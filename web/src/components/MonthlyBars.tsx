import { useEffect, useRef, useState } from "react";
import { fmtInt, fmtMonth } from "../format";

type Point = { month: string; value: number };

/** Bars per month (one series, so the title names it and no legend is needed). */
export default function MonthlyBars({ data, label }: { data: Point[]; label: string }) {
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.max(280, entry!.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const height = 200;
  const pad = { top: 12, right: 8, bottom: 26, left: 44 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const max = Math.max(1, ...data.map((d) => d.value));
  const step = Math.pow(10, Math.floor(Math.log10(max)));
  const top = Math.ceil(max / step) * step;
  const ticks = [0, top / 2, top];
  const slot = innerW / Math.max(1, data.length);
  const barW = Math.max(2, slot - 2); // 2px surface gap between bars
  const y = (v: number) => pad.top + innerH - (v / top) * innerH;
  const every = Math.ceil(data.length / Math.max(1, Math.floor(innerW / 64)));
  const h = hover == null ? null : data[hover];

  return (
    <div className="chart" ref={box}>
      <svg width={width} height={height} role="img" aria-label={label}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.left} x2={width - pad.right} y1={y(t)} y2={y(t)} className="grid" />
            <text x={pad.left - 6} y={y(t)} className="axis" textAnchor="end" dominantBaseline="middle">
              {fmtInt(t)}
            </text>
          </g>
        ))}
        {data.map((d, i) => {
          const x = pad.left + i * slot + 1;
          const top = y(d.value);
          const bh = Math.max(0, pad.top + innerH - top);
          const r = Math.min(4, bh, barW / 2);
          // Rounded only at the data end, square on the baseline.
          const path = `M${x},${pad.top + innerH}V${top + r}Q${x},${top} ${x + r},${top}H${x + barW - r}Q${x + barW},${top} ${x + barW},${top + r}V${pad.top + innerH}Z`;
          return (
            <g key={d.month} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <rect x={pad.left + i * slot} y={pad.top} width={slot} height={innerH} fill="transparent" />
              <path d={path} className={hover === i ? "bar is-hover" : "bar"} />
              {i % every === 0 && (
                <text x={x + barW / 2} y={height - 8} className="axis" textAnchor="middle">
                  {fmtMonth(d.month)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      {h && hover != null && (
        <div
          className="tooltip"
          style={{ left: Math.min(width - 150, Math.max(0, pad.left + hover * slot - 40)), top: Math.max(0, y(h.value) - 52) }}
        >
          <strong>{fmtInt(h.value)}</strong> {label.toLowerCase()}
          <span>{fmtMonth(h.month)}</span>
        </div>
      )}
    </div>
  );
}
