import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Legalo",
    short_name: "Legalo",
    description: "Situation-to-action civic copilot for India",
    start_url: "/",
    display: "standalone",
    background_color: "#f4efe4",
    theme_color: "#1c2438",
  };
}
