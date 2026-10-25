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

export const theme = createTheme({
  primaryColor: "navy",
  primaryShade: 8,
  colors: { navy },
  defaultRadius: "md",
  headings: { fontWeight: "700" },
  components: {
    Paper: { defaultProps: { withBorder: true, radius: "md" } },
    Card: { defaultProps: { withBorder: true, radius: "md", padding: "lg" } },
  },
});
