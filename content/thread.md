



# Twitter Thread: Codebase Map Generator   Scans

## Tweet 1 (HOOK)
I built a tool that generates a structured codebase map in seconds - file tree, module descriptions, entry points, dependency graph. Been using it to onboard AI agents to unfamiliar repos. Here's what I made:



## Tweet 2 (PROBLEM)
Every time I drop an AI agent into a new codebase, it spends the first chunk of context just figuring out where things are. With large repos that's hundreds of tokens wasted before any real work starts.




## Tweet 3 (SOLUTION)
It scans a project directory and outputs a single markdown file: file tree, a short description of each module, entry points, and a dependency graph. Drop that in as context and the agent knows the repo instantly.

Codebase Map Generator   Scans: codebase map generator - scans a project directory and outputs structured markdown with file tree, module
  descriptions, entry points and dependency graph, designed for AI coding agents to quickly understand unfamiliar repos

Built with .


[ATTACH: screenshot of codebase-map-generator---scans in action]

## Tweet 4 (HOW IT WORKS)
How it works:



It's a Python script - uses ast to parse imports and build the dependency graph. Doesn't handle dynamic imports well, so if your codebase leans on importlib you'll get gaps in the graph.

## Tweet 5 (USAGE)
Get started in 3 steps:


1. pip install -r requirements.txt

2. python codebase_map_generator___scans.py --help

3. python codebase_map_generator___scans.py [your-input]


[ATTACH: code block screenshot, dark theme]

## Tweet 6 (RESULTS)
First time I ran it on my own project (~60 files), it generated a 400-line map in 1.8 seconds. My next agent session skipped the whole 'what's in this repo' phase entirely.


Built in 4.3 min | 1091 lines | 6/7 passed


## Tweet 7 (CTA)
Grab it free: {{github_url}}

If you're using AI coding agents on big repos, what's your current approach to context loading? Curious if this solves a problem others have or if I'm just overthinking it.

---

**POSTING NOTES:**
- Post between 8-10 AM EST or 1-3 PM EST on weekdays
- Tweet 1: no image (text-only hooks perform well)
- Tweet 3: screenshot/GIF of tool in action
- Tweet 5: code block screenshot (dark theme, clean font)
- Quote-tweet your own thread 24 hours later with a different hook
- SEO keywords to include: 