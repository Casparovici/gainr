/** A Picnic product picture (Picnic's public image URL), on a white tile (`bg-[#fff]`, not
 * `bg-white`, which the page kit maps to the card colour) so its own white
 * background reads the same in dark mode -- or an empty tile of the same size when there's no
 * picture, so rows with and without one still line up. Decorative: the product's name is always
 * next to it. */
export default function PicnicThumb({ url, size = 32 }: { url: string | null | undefined; size?: number }) {
  return (
    <span
      className="flex shrink-0 items-center justify-center overflow-hidden rounded-lg border border-ui-border bg-[#fff]"
      style={{ width: size, height: size }}
      aria-hidden
    >
      {url && <img src={url} alt="" loading="lazy" className="h-full w-full object-contain p-0.5" />}
    </span>
  );
}
