import json
from html import escape

if __package__:
    from .reports import SKILL_BOARDS
else:
    from reports import SKILL_BOARDS

css = """
*{box-sizing:border-box}
body{margin:0;font-family:"Apple SD Gothic Neo","Noto Sans CJK KR",system-ui,sans-serif;color:#172c26}
.frame{position:relative;width:1080px;height:1350px;padding:72px 76px 58px;background:#f0f4e9;overflow:hidden;display:flex;flex-direction:column}
.frame.odd{background:#f8f5ea}
.mono{font-family:Menlo,monospace;font-variant-numeric:tabular-nums}
.mast,.foot{position:relative;display:flex;justify-content:space-between;align-items:center;gap:24px}
.mast{padding-bottom:28px;border-bottom:2px solid #a7b6a3;font-size:24px;font-weight:750}
.series{display:flex;gap:14px;align-items:center}
.series::before{content:"";height:18px;width:18px;border-radius:50%;background:#31774e}
.issue{font-size:22px;letter-spacing:.01em}
.rank-line{display:flex;justify-content:space-between;align-items:center;margin:62px 0 32px}
.rank{font-size:132px;letter-spacing:-.12em;line-height:1;font-weight:800;color:#1b6043}
.rank span{font-size:30px;color:#426a54;letter-spacing:0;vertical-align:top;margin-right:12px}
.stars{min-width:210px;text-align:right;padding:16px 20px 14px;border:2px solid #aac1a8;border-radius:19px}
.stars strong{display:block;font-size:38px;color:#195d3e;line-height:1.15}
.stars small{font-size:20px;color:#385747;font-weight:750}
.repo{font-size:30px;font-weight:650;color:#38644d;overflow-wrap:anywhere;margin:10px 0 0}
.skill .repo{font-size:46px;margin-top:90px}
.skill .provider{font-size:23px;margin:10px 0 0;color:#38644d;overflow-wrap:anywhere}
h1{font-size:88px;line-height:1.05;letter-spacing:-.068em;word-break:keep-all;overflow-wrap:anywhere;text-wrap:balance;margin:35px 0 28px}
.copy{margin-top:18px}
.copy p{font-size:42px;line-height:1.34;letter-spacing:-.025em;word-break:keep-all;overflow-wrap:break-word;margin:0}
.example{padding:29px 32px;margin-top:42px;background:#e1ead9;border-left:6px solid #478362;border-radius:0 18px 18px 0}
.example b{display:block;font-size:20px;letter-spacing:.015em;color:#235940;margin-bottom:9px}
.example p{font-size:32px}
.foot{margin-top:auto;border-top:2px solid #a7b6a3;padding-top:23px;font-size:22px;color:#375340}
.foot .source{font-weight:700}
.cover{background:#102e25;color:#f9f7e7}
.cover .mast,.cover .foot{border-color:#58816b}
.cover .series::before{background:#c9f07e}
.cover .issue,.cover .foot{color:#cee1cd}
.cover h1{margin:94px 0 0;font-size:102px;text-wrap:initial}
.cover h1 span{display:block;font-size:220px;line-height:1.02;color:#c9f07e;letter-spacing:-.1em}
.cover .intro{font-size:36px;line-height:1.38;margin:28px 0 0;letter-spacing:-.035em;max-width:720px;word-break:keep-all}
.cover-rule{width:100%;height:142px;display:grid;grid-template-columns:repeat(10,1fr);gap:10px;align-items:end;margin-top:46px}
.cover-rule span{height:var(--bar);background:#a6d869;border-radius:8px 8px 0 0}
"""

def page(body):
    return '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>' + css + '</style>' + body + '</html>'

def render(report, stage, reused=()):
    week = report["week"]
    collected_date = report["collected_at"][:10].replace("-", ".")
    board = report.get("board")
    meta = SKILL_BOARDS.get(board)
    label = meta["label"] if meta else "GitHub Trending"
    metric = meta["metric"] if meta else "주간 스타"
    metric_key = "metric_value" if meta else "weekly_stars"
    scope = meta["scope"] if meta else "GitHub 주간 Trending에 오른 저장소 중 주간 스타 수로 집계한 순위입니다."
    heading = f"{label} TOP 10" if meta else "GitHub 주간 Trending TOP 10"
    cover_heading = {"skill-leaderboard": "Skill<br>Leaderboard", "skills-sh": "skills.sh"}.get(
        board, "GitHub 주간<br>Trending",
    )

    def mast(issue):
        return f'<header class="mast"><div class="series">{label}</div><div class="issue mono">{issue}</div></header>'

    slides = stage / "slides"
    slides.mkdir(exist_ok=True)
    most_stars = max(1, report["repositories"][0][metric_key])
    bars = "".join(
        f'<span style="--bar:{item[metric_key] / most_stars * 100:.1f}%"></span>'
        for item in report["repositories"]
    )
    cover = f'''<main class="frame cover">{mast(week)}
      <h1>{cover_heading}<span class="mono">TOP 10</span></h1>
      <p class="intro">{scope}</p>
      <div class="cover-rule" aria-hidden="true">{bars}</div>
      <footer class="foot"><span>{metric} 순</span><span class="mono">{collected_date} KST</span></footer>
    </main>'''
    (slides / "00-cover.html").write_text(page(cover), encoding="utf-8")
    for repo in report["repositories"]:
        rank = repo["rank"]
        if rank in reused:
            continue
        name = escape(repo["name"])
        headline = escape(repo["headline"])
        summary = escape(repo["summary"])
        example = escape(repo["use_case"])
        source = f"{label} 공개 설명" if board else (
            "GitHub 저장소 설명" if repo["readme_url"] == repo["url"] else "GitHub README"
        )
        example_block = f'<section class="example"><b>이럴 때 써요</b><p>{example}</p></section>' if example else ""
        frame_style = "skill" if board else ("odd" if rank % 2 else "")
        ranking = "" if board else f'''<div class="rank-line"><div class="rank mono"><span>#</span>{rank:02d}</div>
      <div class="stars"><strong class="mono">+{repo[metric_key]:,}</strong><small>{metric}</small></div></div>'''
        provider = f'<p class="provider mono">{escape(repo["id"].rsplit("/", 1)[0])}</p>' if board == "skills-sh" else ""
        body = f'''<main class="frame {frame_style}">{mast("" if board else week)}
      {ranking}
      <p class="repo mono">{name}</p>
      {provider}
      <h1>{headline}</h1>
      <div class="copy"><p>{summary}</p>{example_block}</div>
      <footer class="foot"><span>{label}</span><span class="source">출처 · {source}</span></footer>
    </main>'''
        (slides / f"{rank:02d}.html").write_text(page(body), encoding="utf-8")

    package = stage / "package"
    package.mkdir(exist_ok=True)
    blurb = """
    *{box-sizing:border-box}body{max-width:1120px;margin:auto;padding:36px 24px 60px;background:#f0f4e9;color:#172c26;font-family:system-ui,sans-serif}
    header{margin-bottom:26px}header p{color:#355746}h1{margin:.3em 0;line-height:1.1;letter-spacing:-.04em}a{color:#1b6043}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:24px;list-style:none;padding:0}
    li{background:#fcfcf8;border:1px solid #b3c1b0;border-radius:16px;overflow:hidden}img{display:block;width:100%;height:auto}
    .caption{padding:14px 16px 20px}h2{font-size:1.05rem;margin:0 0 6px;overflow-wrap:anywhere}.caption p{font-size:.95rem}.links{display:flex;flex-wrap:wrap;gap:12px}
    """
    items = [
        f'<li><img src="00-cover.png" width="1080" height="1350" alt="{heading} 표지">'
        '<div class="caption"><h2>표지</h2><a href="00-cover.png" download>PNG 다운로드</a></div></li>'
    ]
    for repo in report["repositories"]:
        rank = repo["rank"]
        name = escape(repo["name"])
        summary = escape(repo["summary"])
        example = escape(repo["use_case"])
        count = f'{repo[metric_key]:,}'
        alt = escape(f'{rank}위 {repo["name"]}, {metric} {count}. {repo["headline"]}')
        png = f"{rank:02d}.png"
        source = "스킬 원문" if board == "skills-sh" else (
            "GitHub 저장소" if repo["readme_url"] == repo["url"] else "README 원문"
        )
        items.append(f'''<li><img src="{png}" width="1080" height="1350" loading="lazy" alt="{alt}">
        <div class="caption"><h2>{rank:02d}. {name}</h2><p>{metric} {count}</p><p>{summary}</p>{f"<p>{example}</p>" if example else ""}
        <div class="links"><a href="{png}" download>PNG 다운로드</a><a href="{escape(repo["readme_url"])}">{source}</a></div></div></li>''')

    report_link = f"../../../{board}/weeks/{week}.html" if board else f"../../weeks/{week}.html"
    (package / "index.html").write_text(f'''<!doctype html><html lang="ko"><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1"><title>{week} {label} 카드뉴스</title>
    <style>{blurb}</style><main><header><p>{week} · {collected_date} KST 수집</p>
    <h1>{heading}</h1><p>{scope}</p>
    <a href="{report_link}">주간 순위 리포트</a></header>
    <ol class="grid">{''.join(items)}</ol></main></html>''', encoding="utf-8")
    (package / "cards.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
