import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

APP_DIR = Path(__file__).resolve().parent
GENERATOR = APP_DIR / 'x1_despatch_label_real_diagram.py'


def browse_input():
    path = filedialog.askopenfilename(
        title='Select X1 Quote Schedule PDF',
        filetypes=[('PDF files', '*.pdf')],
    )
    if path:
        input_var.set(path)
        if not output_var.get():
            p = Path(path)
            output_var.set(str(p.with_name(p.stem + '_despatch_label.pdf')))


def browse_output():
    path = filedialog.asksaveasfilename(
        title='Save Despatch Label PDF As',
        defaultextension='.pdf',
        filetypes=[('PDF files', '*.pdf')],
    )
    if path:
        output_var.set(path)


def run_generator():
    input_path = Path(input_var.get().strip())
    output_path = Path(output_var.get().strip())

    if not input_path.is_file():
        messagebox.showerror('Error', 'Please choose a valid X1 Quote Schedule PDF.')
        return
    if not output_path.parent.exists():
        messagebox.showerror('Error', 'The output folder does not exist.')
        return
    if not GENERATOR.is_file():
        messagebox.showerror('Error', f'Cannot find generator script:\n{GENERATOR}')
        return

    run_btn.config(state='disabled')
    status_var.set('Working... please wait.')
    root.update_idletasks()

    cmd = [sys.executable, str(GENERATOR), '--input', str(input_path), '--output', str(output_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        status_var.set('Done.')
        messagebox.showinfo('Finished', f'Despatch label created successfully:\n\n{output_path}')
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or '').strip()
        stdout = (e.stdout or '').strip()
        details = stderr or stdout or 'Unknown error.'
        status_var.set('Failed.')
        messagebox.showerror('Generation failed', details)
    finally:
        run_btn.config(state='normal')


root = tk.Tk()
root.title('X1 Despatch Label Generator')
root.geometry('640x250')
root.resizable(False, False)

main = tk.Frame(root, padx=16, pady=16)
main.pack(fill='both', expand=True)

intro = tk.Label(
    main,
    text='Choose an X1 Quote Schedule PDF, then export a Despatch Label PDF.',
    anchor='w',
    justify='left',
)
intro.grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 14))

input_var = tk.StringVar()
output_var = tk.StringVar()
status_var = tk.StringVar(value='Ready.')


tk.Label(main, text='Input PDF').grid(row=1, column=0, sticky='w')
input_entry = tk.Entry(main, textvariable=input_var, width=62)
input_entry.grid(row=2, column=0, sticky='we', padx=(0, 8))
tk.Button(main, text='Browse...', command=browse_input, width=12).grid(row=2, column=1, sticky='w')


tk.Label(main, text='Output PDF').grid(row=3, column=0, sticky='w', pady=(14, 0))
output_entry = tk.Entry(main, textvariable=output_var, width=62)
output_entry.grid(row=4, column=0, sticky='we', padx=(0, 8))
tk.Button(main, text='Browse...', command=browse_output, width=12).grid(row=4, column=1, sticky='w')

run_btn = tk.Button(main, text='Generate Despatch Label', command=run_generator, width=24, height=2)
run_btn.grid(row=5, column=0, sticky='w', pady=(18, 10))

status_label = tk.Label(main, textvariable=status_var, anchor='w', justify='left')
status_label.grid(row=6, column=0, columnspan=3, sticky='w')

note = tk.Label(
    main,
    text='Note: this version is built for X1 Quote Schedule style PDFs.\nIf your input layout changes a lot, the output may need adjustment.',
    anchor='w',
    justify='left',
)
note.grid(row=7, column=0, columnspan=3, sticky='w', pady=(12, 0))

main.columnconfigure(0, weight=1)
root.mainloop()
