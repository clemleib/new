# Interview prep: Citi Full Stack Support Engineer, VP (Mississauga)

Role focus: **lead application support** for high-impact banking systems using SQL, ETL (Spark or Ab Initio), Unix shell, Python and microservices. You'll also **mentor analysts**, **turn business needs into requirements**, **spot risk and security issues**, and **explain business impact** to stakeholders.

They are hiring a **VP**, so they want a calm incident leader who protects the business, not just someone who fixes tickets. Pair every technical answer with impact, controls and how you'd lead the team.

---

## 1. Your 30-second project pitch

> "To prepare, I built a small payments platform (three Python microservices, a SQL ledger and a nightly settlement ETL) and broke it on purpose: a database connection-pool outage, duplicate postings, a malformed batch file and a rounding bug. Then I built the toolkit I'd want as a support lead: shell triage for the logs, SQL for blast radius and reconciliation, a Python health check with RAG status, and a repair script that only runs as a dry run unless you give it a ticket, and is safe to run twice. Each failure has a runbook a junior analyst could follow, and there's a blameless postmortem. It covers the same skills as the job description."

## 2. Five-minute live demo (practise this twice tonight)

| Step | Command | What to say |
|---|---|---|
| 1 | `python3 app/simulate.py` | "A business day, about 600 payments, with faults injected." |
| 2 | `python3 toolkit/healthcheck.py` | "First question in any incident: what's broken and how badly? Ledger is RED: 4.3% error rate, 25 stuck payments, 120k at risk." |
| 3 | `./toolkit/triage.sh` | "One service, starts at 14:06, peaks at 14:15, *and* slow responses from 13:55. That's resource exhaustion, and a missed early warning." |
| 4 | `./toolkit/trace_txn.sh TXN000405` | "The transaction ID works as a correlation ID across services: received, validated, three retries, failed. The network settled it but our ledger didn't post it." |
| 5 | `python3 toolkit/run_sql.py toolkit/sql/01_stuck_payments.sql` | "Blast radius for the business update: 25 payments, 8 clients, by currency and by 5-minute window." |
| 6 | `python3 toolkit/repost_stuck.py` then add `--apply --ticket INC0012345` | "Dry run by default, requires a ticket, safe to run twice, one transaction, audit logged. That's how I'd want my team changing production data." |
| 7 | `python3 toolkit/healthcheck.py` | "Stuck payments GREEN. Duplicates still RED: that's a different root cause, and a reminder not to assume one incident per day." |

Bonus if there's time: `toolkit/sql/02_duplicates.sql` (window functions) and `toolkit/sql/05_query_tuning.sql` (query plan before and after an index).

If you can't share a screen, walk through the README tables and the postmortem instead.

## 3. Stories to prepare from YOUR experience (STAR, about 2 minutes each)

Use real examples from your own work; the project only backs them up. For each one, have a number ready (time to restore, value, volume, % reduction).

1. **A P1 you led:** how you ran the bridge, who you pulled in, what you told the business, and how fast you restored service.
2. **A root cause you found that others missed:** the SQL or log analysis that cracked it.
3. **Reducing toil or repeat incidents:** automation, monitoring, or a problem ticket that removed a whole class of incidents.
4. **Mentoring a junior analyst:** how you assigned work, built runbooks, and what they can do now.
5. **Turning a business need into a technical requirement:** working with product owners and business analysts on an enhancement, and how you defined scope.
6. **Pushing back:** you stopped a risky change or a production fix without approval. This shows control discipline, which banks value highly.
7. **Communicating impact to a senior non-technical stakeholder.**

## 4. Likely technical questions with crisp answers

**SQL**
- *Find duplicates:* `GROUP BY` the business key `HAVING COUNT(*) > 1`; use `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)` to pick which copy to keep (see `02_duplicates.sql`).
- *Records in A not in B:* `LEFT JOIN ... WHERE b.key IS NULL`, or `NOT EXISTS`. Watch out: `NOT IN` returns nothing if the subquery contains a NULL.
- *Slow query:* read the plan (`EXPLAIN`), look for full scans, check indexes and statistics, check for locking and blocking sessions, and check for functions on indexed columns. Test in UAT before production.
- *WHERE vs HAVING; INNER vs LEFT JOIN; RANK vs DENSE_RANK vs ROW_NUMBER; DELETE vs TRUNCATE.*
- *Production data fix:* ticket and approval first, back up or select the rows before changing them, run in a transaction, check the row count, have a rollback script, and get a second person to review.

**Unix and shell**
- Logs: `grep -c`, `grep -A/-B` for context, `tail -f`, `awk` for fields, `sort | uniq -c | sort -rn` for counting.
- Server checks: `df -h` (disk), `du -sh *`, `free -m`, `top` / `ps -ef`, `lsof` (open files and ports), `netstat` / `ss`, `find -mtime`.
- A process is "running but doing nothing": check CPU in `top`, take a thread dump, check DB locks, and look at what it's waiting on.
- Batch scheduling: cron, and enterprise schedulers such as Autosys or Control-M (job dependencies, reruns, force-start, putting a job on hold).

**ETL (Spark / Ab Initio)**
- Controls: header and trailer counts, reconciling control totals, reject files, **idempotent re-runs**, a batch control or audit table (see `etl_load.py`).
- Spark: a lazy-evaluation DAG; stages are split at shuffles; skew means one slow task; out-of-memory errors call for repartitioning, broadcast joins and executor memory tuning. Use the Spark UI to find the slow stage.
- Ab Initio vocabulary: graphs, components, parallel partitions, EME (version control), sandboxes, plans and Conduct>It. If you haven't used it, say so honestly and relate it to the ETL tools you know.

**Microservices**
- Correlation or trace IDs across services; centralised logging (Splunk / ELK); metrics and APM (for example AppDynamics, Grafana).
- Failure patterns: timeouts plus **retries with backoff**, circuit breakers, **idempotency keys** (the duplicates fault in this project), dead-letter queues, bulkheads.
- Kubernetes or OpenShift basics: pods, a restart loop (CrashLoopBackOff), `kubectl logs/describe`, readiness and liveness probes.

**ITIL and operations**
- Incident (restore fast) vs problem (remove the root cause) vs change (controlled, approved, with a rollback plan).
- SLA (promise to the business) vs SLO (internal target) vs SLI (what you measure). Track mean time to detect and mean time to restore.
- A blameless postmortem whose actions cover detect, prevent, recover and people.

## 5. VP-level questions: how to frame answers

- **"How would you run a P1?"** Take the incident-commander role (or assign it) and open a bridge. Assign roles: technical lead, comms and scribe. Restore service first, investigate root cause later. Send timed updates covering impact, status and next update time. Hold a postmortem within 48 hours, with each action owned and dated.
- **"How do you reduce incident volume?"** Use trend data to find the top 5 recurring incidents. Raise problem tickets, automate the repetitive fixes, alert on warning signs (latency, queue depth) rather than outright failures, and build runbooks and a shift-left knowledge base.
- **"How do you develop a team?"** Runbooks plus shadowing and then reverse shadowing on call, rotate ownership of applications, drills (like `simulate.py`), and clear escalation paths. Measure growth by how many incidents they close without you.
- **"Business vs technology conflict?"** Translate the issue into impact: money, clients, regulatory exposure and deadlines. Give options with trade-offs, and record the decision.

## 6. Citi context to show you've done your homework

Check the latest news before the interview; these are well-known public stories:
- **Risk and controls transformation.** Since the 2020 regulatory consent orders on risk management, data governance and internal controls, Citi has been running a large multi-year programme to modernise and simplify. Regulators fined Citi again in 2024 for slow progress on data management. *Support teams are on the front line of this: data quality, controls, evidence and audit trails.*
- **Operational errors in payments.** The 2020 Revlon case (about $900M sent in error through a manual loan-system process) and a widely reported 2024 near-miss where an account was wrongly credited with a huge sum before it was caught. *Use these to explain why your toolkit defaults to dry runs, requires a ticket and is safe to run twice. Manual production changes need controls.*
- **Services business.** Treasury & Trade Solutions (payments and liquidity) is one of Citi's core franchises, so payments reliability is directly tied to revenue.

Keep it respectful: "I know controls and data quality are a big priority at Citi right now, and that's how I approach support."

## 7. Questions to ask them

1. Which applications would this team support, and what does a typical P1 look like today?
2. What are the biggest sources of incidents or toil right now, and what has the team already tried?
3. How big is the team, how is it split across regions, and what's the mix of experience among the analysts I'd lead?
4. What's the monitoring and tooling stack (Splunk, AppDynamics, Autosys, ServiceNow, OpenShift)?
5. How is support involved in change and release? Does support sign off on production readiness?
6. What would success look like in my first 90 days?

## 8. Night-before checklist
- [ ] Run the demo twice from a clean terminal; make the font large enough to read on a shared screen.
- [ ] Have the README and postmortem open in tabs in case the demo can't run.
- [ ] Write one line of numbers for each STAR story.
- [ ] Re-read the job description and match each bullet to one story.
- [ ] Check this week's Citi news headlines.
