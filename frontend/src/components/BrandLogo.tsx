import { BRAND_NAVY } from "../theme";

/** Chui Labs mark: navy square, wordmark set bottom-right (after the Chui letterhead). */
export function BrandLogo({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" role="img" aria-label="Chui Labs">
      <rect width="100" height="100" fill={BRAND_NAVY} />
      <text x="88" y="60" textAnchor="end" fill="#fff" fontSize="27" fontWeight="500" fontFamily="inherit">
        Chui
      </text>
      <text x="88" y="84" textAnchor="end" fill="#fff" fontSize="21" fontWeight="400" fontFamily="inherit">
        Labs
      </text>
    </svg>
  );
}
