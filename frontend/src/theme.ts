import { createTheme, type MantineColorsTuple } from "@mantine/core";

// Chui Labs navy. Shade 9 is the logo colour.
const navy: MantineColorsTuple = [
  "#eef1f8",
  "#dce2f0",
  "#b5c1de",
  "#8b9ecb",
  "#6880bb",
  "#516db1",
  "#4462ad",
  "#354f8f",
  "#26396b",
  "#1b2a5e",
];

export const BRAND_NAVY = navy[9];

// A tactics sheet, not an admin panel: one sans for the interface, one serif for questions and findings,
// no borders by default (only the selected or winning item gets a navy top rule, see app.css).
export const SERIF = '"Newsreader", "Source Serif 4", Georgia, "Times New Roman", serif';
const SANS = '"IBM Plex Sans", "Segoe UI", system-ui, -apple-system, sans-serif';

export const theme = createTheme({
  primaryColor: "navy",
  primaryShade: 8,
  colors: { navy },
  fontFamily: SANS,
  headings: { fontFamily: SERIF, fontWeight: "600" },
  defaultRadius: "sm",
  components: {
    Paper: { defaultProps: { withBorder: false, radius: "sm" } },
    Card: { defaultProps: { withBorder: false, radius: "sm", padding: "lg" } },
  },
});
