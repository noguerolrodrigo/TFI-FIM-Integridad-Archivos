# Abstract

This work presents the design, implementation and evaluation of an automated File Integrity
Monitoring (FIM) system for Linux. The system reacts to kernel events (inotify, through the Python
watchdog library) and compares the actual state of each file with a versioned baseline stored in
PostgreSQL. In this way it classifies the change (modification, creation, deletion, move or
permission change) and stores the evidence: the previous and new SHA-256 hashes, a copy of the
altered file and, for text files, the diff of the changed lines.

As a response, it restores the file from a copy verified against the database or isolates it in
quarantine, with an approval mode and maintenance windows to avoid reverting legitimate changes.
With n8n, each alert arrives through Telegram with buttons to confirm the incident, restore the
file or accept the change, and the monitor executes the decision. The log is append-only and each
component runs with minimum privileges.

In a laboratory on WSL2, with 50 repetitions of five types of change, detection had a median of
5.4 ms and restoration a median of 45.4 ms, dominated by the write to the database. The alert
reached Telegram with a median of 1.11 s, over ten alerts with the real bot. The temporary-file
filter lowered the proportion of spurious alerts when editing with two editors from 50.0 % and
66.7 % to 0 %. With one scan per minute, the estimated mean detection time would be about 30 s. In
the second evaluation instance, security defects in the restoration were corrected; a new run on
the corrected version showed no distinguishable changes in these metrics, except for the
restoration of a 1 MB binary file, which was about 3 ms slower. The results correspond to a single
environment and their limitations are detailed in the report.

**Keywords:** file integrity monitoring, FIM, inotify, SHA-256, differential evidence, incident
response, n8n.
