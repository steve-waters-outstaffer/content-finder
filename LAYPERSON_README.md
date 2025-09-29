# Outstaffer Content Finder & Intelligence Engine (Plain-English Guide)

Welcome! This guide explains, in everyday language, what the Outstaffer Content Finder app does and how the two main parts—the **Content Finder** and the **Intelligence Engine**—work together to surface recruitment and Employer of Record (EOR) insights.

---

## Big Picture

1. **Content Finder** helps a researcher quickly search the web, pull down articles, and get an AI-written summary or mash-up.
2. **Intelligence Engine** runs a more structured research project: it plans the searches, checks sources, and turns them into strategic talking points for different customer segments.

Both areas rely on a few trusted services:
- **Tavily**: an online search service. Think of it as a smarter Google that returns clean links for research queries.
- **Firecrawl**: a web scraper. It fetches the actual article text from a link so we can read and analyze it.
- **Gemini (Google’s AI model)**: the AI brain that reads long articles and produces human-friendly summaries, bullet points, and strategy ideas.

---

## Part 1 – Content Finder

### What it does
- Lets you type a topic (for example, “SMB hiring trends 2025”).
- Uses Firecrawl’s search feature to grab a list of promising articles.
- Lets you click a link and automatically fetch the article text.
- Sends that text to Gemini so you instantly get a short brief (summary, key insights, Outstaffer angle, suggested next steps, etc.).
- Allows you to star-rate the article quality and the AI summary so your team can keep track of what’s useful.
- Lets you select multiple good articles and ask Gemini to stitch them into one combined research piece with ready-to-use insights and even a LinkedIn post idea.

### How the flow works (step by step)
1. **Search** – When you hit “Search,” the app calls a backend endpoint that uses Firecrawl’s search API to look up your topic and return a list of URLs.【F:src/components/ContentFinder.jsx†L57-L118】【F:backend/core/firecrawl_client.py†L10-L69】
2. **Pick sources** – You can scan the list, open the articles, and mark the ones you care about. Quick chips with pre-made topics help you start fast.【F:src/components/ContentFinder.jsx†L32-L55】【F:src/components/ContentFinder.jsx†L311-L373】
3. **Process a single article** – Clicking “Process” first asks Firecrawl to scrape the web page, then passes the scraped text to Gemini for an AI breakdown tailored to Outstaffer (summary, key insights, how it helps, actions).【F:src/components/ContentFinder.jsx†L120-L214】【F:backend/core/firecrawl_client.py†L71-L115】【F:backend/core/gemini_client.py†L57-L127】
4. **Rate and review** – The processed article shows the AI insight and the underlying source text. You can rate both to record quality feedback for later (stored locally today, with TODOs to save it in a database).【F:src/components/ContentFinder.jsx†L215-L332】
5. **Synthesize multiple pieces** – After selecting several strong sources, you can run “Synthesize.” The app re-scrapes the chosen links, then asks Gemini to weave everything into a narrative, highlight opportunities for Outstaffer, and draft a social post angle.【F:src/components/ContentFinder.jsx†L216-L309】【F:src/components/ContentFinder.jsx†L333-L409】【F:backend/core/gemini_client.py†L19-L55】
6. **See the numbers** – A summary widget shows how many articles were found, scraped, and turned into combined research so you always know your progress.【F:src/components/ContentFinder.jsx†L374-L408】

### Why it’s helpful
- Cuts down manual copy/paste work.
- Keeps the raw article text and the AI summary side-by-side.
- Gives you a fast “report” when stakeholders want a point of view on a trend.

---

## Part 2 – Intelligence Engine

### What it does
- Sets up monthly “research missions” for specific customer segments (for example, “US staffing leaders”).
- Uses Gemini to draft a smart list of search queries tailored to each segment’s priorities.
- Uses Tavily to run those queries and Firecrawl to fetch the most relevant sources.
- Guides you through a three-step workflow: plan queries → review search hits → generate strategy themes.
- Stores the research output in organized monthly folders so you can reuse it or share it later.

### How the flow works (step by step)
1. **Choose a segment** – The dashboard lists each audience segment pulled from the monthly config. Pick one to start a research session.【F:src/components/intelligence/IntelligenceDashboard.jsx†L20-L96】
2. **Create a session** – Give the mission a quick tweak if needed and press “Start.” This logs the session and prepares to generate queries.【F:src/components/IntelligenceSteps/SessionWorkflow.jsx†L30-L120】
3. **Generate queries (Phase 1)** – Gemini reads the mission brief and produces a set of focused web searches. You can toggle or edit them before moving on.【F:src/components/IntelligenceSteps/QueryGeneration.jsx†L1-L126】【F:backend/intelligence/agent_research.py†L34-L109】
4. **Search sources (Phase 2)** – For each approved query, the backend leans on Tavily to find strong links, then Firecrawl to grab article passages for deeper review.【F:backend/intelligence/agent_research.py†L111-L168】【F:backend/core/tavily_client.py†L1-L23】
5. **Analyze content (Phase 3)** – Gemini reads the collected passages and produces a segment-specific briefing: talking points, campaign ideas, and other strategy-ready content.【F:backend/intelligence/agent_research.py†L170-L231】【F:backend/core/gemini_client.py†L57-L127】
6. **Keep records** – Each run saves research results, processing plans, and AI outputs in an `intelligence_runs/<month>` folder. That makes it easy to track what was covered and share the findings with marketing or sales later.【F:backend/intelligence/intelligence_engine.py†L13-L74】

### Why it’s helpful
- Delivers repeatable intelligence for key customer personas without a ton of manual effort.
- Keeps human decision-makers in the loop—people still review and approve queries and sources.
- Produces polished insights, not just raw links, so marketing and sales teams can act fast.

---

## Putting It All Together

- Use **Content Finder** when you need quick answers or a rapid-fire research brief on a single topic.
- Use the **Intelligence Engine** when you’re running an in-depth campaign or monthly briefing for a target segment.
- Both tools rely on the same trio of services—Tavily, Firecrawl, and Gemini—to make web research faster and smarter.

If you ever wonder “where did this insight come from?”, the app keeps the original links, the scraped text, and the AI notes side-by-side so you can double-check the facts and keep stakeholders confident in the output.

Happy researching! 🚀
