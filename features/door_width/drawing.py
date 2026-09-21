"""Conservative reader for X1's 720x660 embedded elevation drawings.

OCR supplies numeric evidence only. Width arithmetic never uses measured pixels
or rail lengths. Image geometry locates sections and full-height hinge symbols.
Other raster layouts return manual review instead of a guessed configuration.
"""
from functools import lru_cache
import re
import threading
import numpy as np
import pymupdf


class DrawingUnclear(ValueError):
    pass


_ocr_lock=threading.Lock()


@lru_cache(maxsize=1)
def ocr_engine():
    from rapidocr_onnxruntime import RapidOCR
    return RapidOCR(intra_op_num_threads=2,inter_op_num_threads=2)


def read_labels(gray, binary, lo, hi):
    import cv2
    band=binary[lo:hi].copy()
    horizontal=cv2.morphologyEx(band,cv2.MORPH_OPEN,np.ones((1,35),np.uint8))
    vertical=cv2.morphologyEx(band,cv2.MORPH_OPEN,np.ones((38,1),np.uint8))
    clean=cv2.subtract(band,cv2.bitwise_or(horizontal,vertical))
    _,_,stats,_=cv2.connectedComponentsWithStats(clean)
    boxes=sorted((int(x),int(y),int(x+w),int(y+h)) for x,y,w,h,area in stats[1:]
                 if h>=18 and w>=3 and area>=35)
    merged=[]
    for box in boxes:
        if merged and box[0]-merged[-1][2]<13:
            a=merged[-1]; merged[-1]=(a[0],min(a[1],box[1]),max(a[2],box[2]),max(a[3],box[3]))
        else:
            merged.append(box)
    labels=[]
    for x,y,xx,yy in merged:
        crop=gray[lo+max(y-2,0):lo+yy+2,max(x-2,0):xx+2]
        crop=cv2.copyMakeBorder(crop,10,10,10,10,cv2.BORDER_CONSTANT,value=255)
        with _ocr_lock:
            result,_=ocr_engine()(cv2.cvtColor(crop,cv2.COLOR_GRAY2BGR),use_det=False,use_cls=False)
        if not result or len(result)!=1:
            raise DrawingUnclear('A dimension could not be read reliably.')
        text,confidence=result[0]
        if not re.fullmatch(r'\d{2,5}(?:\.\d+)?',text) or confidence<.985:
            raise DrawingUnclear('A dimension has low OCR confidence; check the drawing manually.')
        labels.append(dict(value=float(text),confidence=float(confidence),x=(x+xx)/2))
    return labels


def has_hinge(binary, left, right, top, bottom):
    import cv2
    width=right-left; height=bottom-top
    crop=binary[top:bottom+1,int(left):int(right)+1]
    lines=cv2.HoughLinesP(crop,1,np.pi/180,threshold=25,
                         minLineLength=int(height*.25),maxLineGap=14)
    upper=[]; lower=[]
    for x1,y1,x2,y2 in ([] if lines is None else lines.reshape(-1,4)):
        if y1>y2: x1,y1,x2,y2=x2,y2,x1,y1
        if abs(x2-x1)<width*.40 or y2-y1<height*.27:
            continue
        direction=1 if x2>x1 else -1
        if y1<height*.18 and .40*height<y2<.60*height:
            upper.append((direction,x2))
        if .40*height<y1<.60*height and y2>height*.82:
            lower.append((direction,x1))
    return any(a==-b and abs(x-y)<width*.12 for a,x in upper for b,y in lower)


def read_image(image_bytes):
    import cv2
    image=cv2.imdecode(np.frombuffer(image_bytes,dtype=np.uint8),cv2.IMREAD_GRAYSCALE)
    if image is None or image.shape!=(660,720):
        raise DrawingUnclear('This drawing resolution/layout is not verified (expected X1 720 x 660 elevation).')
    binary=(image<130).astype(np.uint8)*255
    horizontal=cv2.morphologyEx(binary,cv2.MORPH_OPEN,np.ones((1,55),np.uint8))
    horizontal=cv2.morphologyEx(horizontal,cv2.MORPH_CLOSE,np.ones((1,10),np.uint8))
    sums=(horizontal>0).sum(axis=1)
    if sums.max()<140:
        raise DrawingUnclear('Could not identify a rectangular frame.')
    rows=np.flatnonzero(sums>=sums.max()*.95)
    top,bottom=int(rows[0]),int(rows[-1])
    xs=np.flatnonzero(horizontal[top]); left,right=int(xs[0]),int(xs[-1])
    if bottom-top<220 or top<60 or bottom>600:
        raise DrawingUnclear('Unrecognised drawing envelope.')
    labels=read_labels(image,binary,0,top-20)
    total_labels=read_labels(image,binary,bottom+20,len(binary))
    if not 1<=len(labels)<=4 or len(total_labels)!=1:
        raise DrawingUnclear('A complete section-width chain and total width are required.')
    widths=[v['value'] for v in labels]
    total=total_labels[0]['value']
    if abs(sum(widths)-total)>.01:
        raise DrawingUnclear('Section widths do not add up to the independent overall width.')
    boundaries=[float(left)]
    for width in widths:
        boundaries.append(boundaries[-1]+width/total*(right-left))
    # Dimensional chain must agree with the observed label positions and frame
    # divisions. Pixel-derived locations never become millimetre dimensions.
    # Item labels sometimes interrupt an otherwise continuous upright.
    joined=cv2.morphologyEx(binary,cv2.MORPH_CLOSE,np.ones((20,1),np.uint8))
    vertical=cv2.morphologyEx(joined,cv2.MORPH_OPEN,np.ones((int((bottom-top)*.7),1),np.uint8))
    for x in boundaries:
        strip=vertical[top:bottom+1,max(0,int(x)-7):min(720,int(x)+8)]
        if not strip.size or (strip>0).sum(axis=0).max()<(bottom-top)*.65:
            raise DrawingUnclear('Width chain does not align with full-height frame divisions (possible top light or different layout).')
    door_indices=[]
    for index,label in enumerate(labels):
        a,b=boundaries[index:index+2]
        if abs(label['x']-(a+b)/2)>max(13,(b-a)*.15):
            raise DrawingUnclear('Dimension label cannot be assigned to its section.')
        if has_hinge(binary,a,b,top,bottom):
            door_indices.append(index)
    if len(door_indices) not in (1,2) or door_indices!=list(range(min(door_indices,default=0),max(door_indices,default=-1)+1)):
        raise DrawingUnclear('Cannot uniquely identify one single/French door from full-height hinge symbols.')
    if door_indices[0]>1 or len(widths)-door_indices[-1]-1>1:
        raise DrawingUnclear('Multiple adjacent sections are outside this rule family.')
    return dict(section_widths=widths,total_width=total,door_indices=door_indices,
                door_width=sum(widths[i] for i in door_indices),
                ocr_confidence=min(v['confidence'] for v in labels+total_labels),
                evidence_method='X1 raster dimension OCR + full-height hinge-symbol and division checks')


def read_drawing(path,page_number):
    with pymupdf.open(path) as pdf:
        page=pdf[page_number-1]
        candidates=[info for info in page.get_images(full=True) if info[2]>=500 and info[3]>=400]
        if len(candidates)!=1:
            raise DrawingUnclear('Expected exactly one embedded elevation drawing on this item page.')
        return read_image(pdf.extract_image(candidates[0][0])['image'])
