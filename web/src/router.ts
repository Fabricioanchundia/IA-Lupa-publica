import { useEffect, useState } from "react";

/** Tiny hash router: "#/entidades/EC-RUC-123?x=1" -> { page: "entidades", id: "EC-RUC-123", params }.
 *  Hash routes work on GitHub Pages without any server configuration. */
export type Route = { page: string; id: string; params: URLSearchParams; key: string };

function parse(): Route {
  const raw = window.location.hash.replace(/^#\/?/, "");
  const [path = "", search = ""] = raw.split("?");
  const [page = "", ...rest] = path.split("/");
  return { page, id: decodeURIComponent(rest.join("/")), params: new URLSearchParams(search), key: raw };
}

export function useRoute(): Route {
  const [route, setRoute] = useState(parse);
  useEffect(() => {
    const onHash = () => {
      setRoute(parse());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  return route;
}

/** Builds "#/page/id?a=b", skipping empty values. */
export function href(page: string, id = "", params: Record<string, string | undefined> = {}): string {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v) search.set(k, v);
  const qs = search.toString();
  return `#/${page}${id ? `/${encodeURIComponent(id)}` : ""}${qs ? `?${qs}` : ""}`;
}
