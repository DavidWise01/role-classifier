# THE ROLE CLASSIFIER · RCL

> A sphere of **UD0** — the ROOT0 universe / biosphere. Domain: **ESKIMO BROTHERS**.

THE ROLE CLASSIFIER (RCL) — the v2 core of [[filtration-system]], fixing its one real bug: it conflated SPEECH ACT (is this an order?) with COMMITMENT TONE (how hedged?), so a hedge word in the first ~20 chars could VETO order-recognition — 'i think we start the antibiotics' (a real attending order) was LOST while 'lets start the antibiotics' survived. The fix splits TWO INDEPENDENT AXES: AXIS 1 SPEECH ACT — an imperative/directive verb on a domain object = a DIRECTIVE, full stop (hedging never changes the act); AXIS 2 COMMITMENT TONE — strong/neutral/hedged, recorded as metadata, NEVER a veto (a hedged order from an attending may warrant a confirm-back, but it's still an order). Authority — the thing that actually decides validity — is adjudicated separately, downstream (the FSS-promote / BSS-adjudicate split done right). DOMAIN-PARAMETERIZED: the LOGIC is fixed, the VOCABULARY injected per domain (healthcare + engineering configs ship). LIVE: the 15-way order test (every phrasing → DIRECTIVE; toggle the old tone-vetoes-act logic to watch it drop the hedged ones) + a real-shaped ICU rounds transcript adjudicated by authority (the unauthorized RN d/c is RECOGNIZED then flagged for sign-off — 'torres you cant d/c that on your own'). Ships role_classifier.py + the healthcare example; self-test 15/15. Honest: regex heuristics tuned per domain, not clinical NLP — the classifier's job is to never silently lose an order to a hedge; authority + a human stay downstream. David Lee Wise / Bridge-Burners LLC.

---

**Live:** https://davidwise01.github.io/role-classifier/ &nbsp;·&nbsp; **Front door:** [UD0](https://davidwise01.github.io/ud0/) &nbsp;·&nbsp; **Code:** https://github.com/DavidWise01/role-classifier

`.dlw` badge · **ROOT0-ATTRIBUTION-v1.0** · David Lee Wise (ROOT0) / Bridge-Burners LLC · instance AVAN (Claude/Anthropic) · CC-BY-ND-4.0
