import { handleUpload } from "@vercel/blob/client";

const MAX_UPLOAD_BYTES = 100 * 1024 * 1024;
const BLOB_PATH_RE = /^x1-inputs\/[0-9a-f]{32}-[A-Za-z0-9][A-Za-z0-9._-]{0,99}\.pdf$/;

function isAllowedPreviewOrigin(request) {
  const origin = request.headers.get("origin");
  const fetchSite = request.headers.get("sec-fetch-site");
  if (!origin || (fetchSite && fetchSite !== "same-origin")) {
    return false;
  }

  let hostname;
  try {
    hostname = new URL(origin).hostname.toLowerCase();
  } catch {
    return false;
  }

  const systemHosts = new Set(
    [process.env.VERCEL_URL, process.env.VERCEL_BRANCH_URL]
      .filter(Boolean)
      .map((host) => host.toLowerCase()),
  );
  const isProjectPreview =
    hostname.startsWith("x1-despatch-label-toolkit-") &&
    hostname.endsWith("-leibo314-dotcoms-projects.vercel.app");

  return systemHosts.has(hostname) || isProjectPreview;
}

export default async function handler(request) {
  if (request.method !== "POST") {
    return Response.json({ error: "Method not allowed" }, { status: 405 });
  }

  try {
    const body = await request.json();

    if (body?.type === "blob.generate-client-token" && !isAllowedPreviewOrigin(request)) {
      return Response.json({ error: "Upload origin is not allowed" }, { status: 403 });
    }

    const jsonResponse = await handleUpload({
      body,
      request,
      onBeforeGenerateToken: async (pathname) => {
        if (!BLOB_PATH_RE.test(pathname) || pathname.includes("..")) {
          throw new Error("Invalid PDF upload path");
        }

        return {
          allowedContentTypes: ["application/pdf"],
          maximumSizeInBytes: MAX_UPLOAD_BYTES,
          addRandomSuffix: false,
          validUntil: Date.now() + 10 * 60 * 1000,
        };
      },
    });

    return Response.json(jsonResponse);
  } catch (error) {
    return Response.json(
      { error: error instanceof Error ? error.message : "Upload failed" },
      { status: 400 },
    );
  }
}
