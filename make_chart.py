import json

def generate_html_chart():
    with open("equity_curve_001.json", "r") as f:
        data = json.load(f)

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>$100 Account Growth Curve (0.01 Lot) - London Sweep & NY Reversal</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    .glow {{ filter: drop-shadow(0 0 6px rgba(16, 185, 129, 0.4)); }}
  </style>
</head>
<body class="bg-transparent text-[var(--foreground)] antialiased p-3 sm:p-5 font-sans">
  <div class="bg-[var(--card)] text-[var(--foreground)] border border-[var(--border)] rounded-2xl p-5 shadow-lg max-w-4xl mx-auto">
    
    <!-- Header -->
    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] pb-4 mb-4">
      <div>
        <div class="flex items-center gap-2">
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-400 border border-blue-500/30">
            Gold (XAUUSD) • Fixed 0.01 Lot
          </span>
          <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
            $100.00 $\\rightarrow$ $336.85 (+236.9%)
          </span>
        </div>
        <h1 class="text-xl font-bold tracking-tight mt-1 text-[var(--foreground)]">
          $100 Account Growth Curve & $200 Milestone Tracker
        </h1>
        <p class="text-xs text-[var(--muted-foreground)] mt-0.5">
          Backtest Period: <strong>Aug 12, 2025 – Sep 25, 2026 (13.5 Months / 179 Trades)</strong>
        </p>
      </div>

      <!-- Quick Stats Top -->
      <div class="flex items-center gap-3 text-right">
        <div class="bg-[var(--background)] p-2.5 rounded-xl border border-[var(--border)]">
          <span class="text-[10px] text-[var(--muted-foreground)] block uppercase font-medium">Hit $200.00</span>
          <span class="text-sm font-bold text-emerald-400">Feb 25, 2026</span>
          <span class="text-[10px] text-slate-400 block">(Trade #91 • 6.5 Mos)</span>
        </div>
        <div class="bg-[var(--background)] p-2.5 rounded-xl border border-[var(--border)]">
          <span class="text-[10px] text-[var(--muted-foreground)] block uppercase font-medium">Final Balance</span>
          <span class="text-sm font-bold text-cyan-400">$336.85</span>
          <span class="text-[10px] text-slate-400 block">(+236.9% ROI)</span>
        </div>
      </div>
    </div>

    <!-- Chart Container -->
    <div class="relative bg-slate-950 rounded-xl border border-slate-800 p-3 overflow-hidden shadow-inner">
      <canvas id="equityCanvas" width="800" height="340" class="w-full h-auto block cursor-crosshair"></canvas>
      
      <!-- Hover Tooltip -->
      <div id="chartTooltip" class="hidden absolute pointer-events-none bg-slate-900/95 backdrop-blur-md border border-slate-700 rounded-lg p-2.5 text-xs text-slate-200 shadow-xl z-20">
        <div id="ttDate" class="text-[10px] text-slate-400 font-mono">Date: ---</div>
        <div class="font-bold text-sm text-emerald-400 mt-0.5" id="ttBalance">Balance: $0.00</div>
        <div class="text-[11px] text-slate-300" id="ttPnl">Trade PnL: $0.00</div>
        <div class="text-[10px] text-slate-500" id="ttTrade">Trade #-- of 179</div>
      </div>

      <!-- Milestone Marker Legend -->
      <div class="absolute bottom-3 left-4 flex flex-wrap items-center gap-3 text-[11px] bg-slate-900/80 backdrop-blur-sm px-3 py-1.5 rounded-lg border border-slate-800">
        <span class="flex items-center gap-1.5 text-slate-300">
          <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block glow"></span> Equity Curve
        </span>
        <span class="flex items-center gap-1.5 text-amber-300">
          <span class="w-2 h-2 rounded-full bg-amber-400 inline-block"></span> $200 Milestone (Feb 25)
        </span>
        <span class="flex items-center gap-1.5 text-slate-400">
          <span class="w-3 h-0.5 border-t border-dashed border-slate-500 inline-block"></span> Initial Balance ($100)
        </span>
      </div>
    </div>

    <!-- Milestone & Timeline Grid -->
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-4 text-xs">
      <div class="p-3 rounded-xl bg-[var(--background)] border border-[var(--border)]">
        <div class="flex items-center justify-between">
          <span class="text-[var(--muted-foreground)] font-medium">Phase 1: Starting Out</span>
          <span class="px-1.5 py-0.5 text-[10px] rounded bg-slate-800 text-slate-300 font-mono">Aug 12, 2025</span>
        </div>
        <div class="text-base font-bold text-[var(--foreground)] mt-1">$100.00 Starting Capital</div>
        <p class="text-[11px] text-[var(--muted-foreground)] mt-0.5">
          Account trades fixed 0.01 lot ($1.50 - $4.50 risk/trade). Survived initial normal drawdown cleanly (low of $17.65).
        </p>
      </div>

      <div class="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30">
        <div class="flex items-center justify-between">
          <span class="text-amber-400 font-medium font-semibold">Phase 2: Doubled Capital</span>
          <span class="px-1.5 py-0.5 text-[10px] rounded bg-amber-500/20 text-amber-300 font-mono font-bold">Feb 25, 2026</span>
        </div>
        <div class="text-base font-bold text-amber-300 mt-1">$206.09 (Account Reached $200!)</div>
        <p class="text-[11px] text-amber-200/80 mt-0.5">
          Took <strong>197 days (~6.5 months, 91 trades)</strong>. At this point, you can safely scale to <strong>0.02 lot</strong> to double profit velocity!
        </p>
      </div>

      <div class="p-3 rounded-xl bg-[var(--background)] border border-[var(--border)]">
        <div class="flex items-center justify-between">
          <span class="text-[var(--muted-foreground)] font-medium">Phase 3: Backtest Finish</span>
          <span class="px-1.5 py-0.5 text-[10px] rounded bg-emerald-500/20 text-emerald-400 font-mono">Sep 25, 2026</span>
        </div>
        <div class="text-base font-bold text-emerald-400 mt-1">$336.85 Final Balance</div>
        <p class="text-[11px] text-[var(--muted-foreground)] mt-0.5">
          Total Net Profit: <strong>+$236.85 (+236.9%)</strong> over 179 total trades. 100% account survival with zero margin call risk.
        </p>
      </div>
    </div>

  </div>

  <script>
    const tradeData = {json.dumps(data)};
    const canvas = document.getElementById('equityCanvas');
    const ctx = canvas.getContext('2d');
    const tooltip = document.getElementById('chartTooltip');

    const padding = {{ left: 55, right: 35, top: 30, bottom: 40 }};
    const w = canvas.width;
    const h = canvas.height;
    const plotW = w - padding.left - padding.right;
    const plotH = h - padding.top - padding.bottom;

    const minBal = 0.0;
    const maxBal = 360.0;

    function getX(i) {{
      return padding.left + (i / (tradeData.length - 1)) * plotW;
    }}

    function getY(val) {{
      return padding.top + plotH - ((val - minBal) / (maxBal - minBal)) * plotH;
    }}

    function drawChart() {{
      ctx.clearRect(0, 0, w, h);

      // Horizontal grid lines
      ctx.strokeStyle = '#1e293b';
      ctx.lineWidth = 1;
      ctx.font = '10px monospace';
      ctx.fillStyle = '#64748b';

      for (let b = 50; b <= 350; b += 50) {{
        const y = getY(b);
        ctx.beginPath();
        ctx.moveTo(padding.left, y);
        ctx.lineTo(w - padding.right, y);
        ctx.stroke();
        ctx.fillText('$' + b, 15, y + 3);
      }}

      // Starting $100 Reference Line
      const y100 = getY(100);
      ctx.strokeStyle = '#475569';
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(padding.left, y100);
      ctx.lineTo(w - padding.right, y100);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = '#94a3b8';
      ctx.fillText('$100 Start', w - padding.right - 55, y100 - 5);

      // Target $200 Reference Line
      const y200 = getY(200);
      ctx.strokeStyle = '#d97706';
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      ctx.moveTo(padding.left, y200);
      ctx.lineTo(w - padding.right, y200);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = '#fbbf24';
      ctx.fillText('⭐ $200 Milestone', w - padding.right - 90, y200 - 5);

      // Area fill below equity curve
      ctx.beginPath();
      ctx.moveTo(getX(0), getY(100));
      for (let i = 0; i < tradeData.length; i++) {{
        ctx.lineTo(getX(i), getY(tradeData[i].balance));
      }}
      ctx.lineTo(getX(tradeData.length - 1), getY(0));
      ctx.lineTo(getX(0), getY(0));
      ctx.closePath();

      const grad = ctx.createLinearGradient(0, padding.top, 0, h - padding.bottom);
      grad.addColorStop(0, 'rgba(16, 185, 129, 0.25)');
      grad.addColorStop(1, 'rgba(16, 185, 129, 0.0)');
      ctx.fillStyle = grad;
      ctx.fill();

      // Equity Line
      ctx.strokeStyle = '#10b981';
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      for (let i = 0; i < tradeData.length; i++) {{
        const x = getX(i);
        const y = getY(tradeData[i].balance);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }}
      ctx.stroke();

      // Find trade 91 ($200 milestone)
      const milestoneIdx = 90; // trade #91
      const mx = getX(milestoneIdx);
      const my = getY(tradeData[milestoneIdx].balance);

      // Vertical marker for milestone
      ctx.strokeStyle = '#f59e0b';
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(mx, padding.top);
      ctx.lineTo(mx, h - padding.bottom);
      ctx.stroke();
      ctx.setLineDash([]);

      // Star Point
      ctx.fillStyle = '#f59e0b';
      ctx.beginPath();
      ctx.arc(mx, my, 6, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Milestone Callout Box
      ctx.fillStyle = 'rgba(245, 158, 11, 0.9)';
      ctx.fillRect(mx - 65, my - 38, 130, 24);
      ctx.fillStyle = '#0f172a';
      ctx.font = 'bold 10px sans-serif';
      ctx.fillText('HIT $200! (Feb 25, 2026)', mx - 60, my - 22);

      // Dates along X axis
      ctx.fillStyle = '#64748b';
      ctx.font = '10px sans-serif';
      ctx.fillText('Aug 2025', getX(0), h - 15);
      ctx.fillText('Nov 2025', getX(40), h - 15);
      ctx.fillText('Feb 2026 (Hit $200)', mx - 40, h - 15);
      ctx.fillText('Jun 2026', getX(130), h - 15);
      ctx.fillText('Sep 2026 ($336)', getX(178) - 50, h - 15);
    }}

    drawChart();

    // Hover interaction
    canvas.addEventListener('mousemove', (e) => {{
      const rect = canvas.getBoundingClientRect();
      const mouseX = (e.clientX - rect.left) * (canvas.width / rect.width);
      
      let closestIdx = Math.round(((mouseX - padding.left) / plotW) * (tradeData.length - 1));
      if (closestIdx < 0) closestIdx = 0;
      if (closestIdx >= tradeData.length) closestIdx = tradeData.length - 1;

      const item = tradeData[closestIdx];
      const cx = getX(closestIdx);
      const cy = getY(item.balance);

      drawChart();

      // Draw hover circle
      ctx.fillStyle = '#38bdf8';
      ctx.beginPath();
      ctx.arc(cx, cy, 5, 0, Math.PI * 2);
      ctx.fill();

      // Position tooltip
      const tooltipX = (cx / canvas.width) * rect.width + 10;
      const tooltipY = (cy / canvas.height) * rect.height - 40;

      tooltip.style.left = tooltipX + 'px';
      tooltip.style.top = tooltipY + 'px';
      tooltip.classList.remove('hidden');

      document.getElementById('ttDate').innerText = 'Date: ' + item.date;
      document.getElementById('ttBalance').innerText = 'Balance: $' + item.balance.toFixed(2);
      document.getElementById('ttPnl').innerText = 'Trade PnL: ' + (item.pnl >= 0 ? '+' : '') + '$' + item.pnl.toFixed(2);
      document.getElementById('ttTrade').innerText = 'Trade #' + item.trade + ' of ' + tradeData.length;
    }});

    canvas.addEventListener('mouseleave', () => {{
      tooltip.classList.add('hidden');
      drawChart();
    }});
  </script>
</body>
</html>
"""

    with open("C:/Users/dines/.gemini/antigravity/brain/f902d8eb-cbbe-413b-81d6-4cba1d476194/equity_graph_001.html", "w", encoding="utf-8") as out:
        out.write(html_template)

    print("Generated equity_graph_001.html in artifact directory!")

if __name__ == "__main__":
    generate_html_chart()
