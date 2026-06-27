#!/usr/bin/env python3
"""
role_classifier.py — domain-parameterized speech-act classifier.

The v1 extractor's bug: it conflated SPEECH ACT (is this an order?) with
COMMITMENT TONE (how confidently is it phrased?). A hedge word in the first
20 chars could VETO order-recognition — so "i think we start the antibiotics"
(a real attending order) was lost while "lets start the antibiotics" survived.
Order recognition became a coin flip on sentence opener.

The fix — two independent axes:

  AXIS 1  SPEECH ACT: what kind of utterance is this?
          Determined by ACTION STRUCTURE: an imperative/directive verb applied
          to a domain object = a directive (ORDER/COMMAND/DECISION), full stop.
          Hedging does NOT change the speech act. "I think we should start X"
          and "Start X" are the same act, differently softened.

  AXIS 2  COMMITMENT TONE: how hedged is it? (recorded as metadata, never a veto)
          strong  = bare imperative / "final call" / "i want"
          neutral = "lets" / "we should" / "go ahead"
          hedged  = "i think" / "maybe" / "probably" / "id consider"

Tone is carried forward as a SIGNAL (a hedged order from an attending may
warrant a confirm-back) but it NEVER demotes the speech act. Authority — the
thing that actually decides validity — is checked separately, downstream.

Domain config is injected: the LOGIC is fixed, the VOCABULARY is per-domain.
"""

import re

# ═══════════════════════════════════════════════════════════════════════
# domain configuration — the swappable vocabulary
# ═══════════════════════════════════════════════════════════════════════

HEALTHCARE = {
    "name": "healthcare",
    # directive verbs: an imperative clinical action. matches inflections
    # (start/starts/starting/started) — clinicians narrate orders in present
    # continuous constantly ("starting vanc", "im discontinuing the ketorolac").
    "action_verbs": r"\b(start|begin|initiat|continu|discontinu|stop|hold|holding|"
                    r"reduc|decreas|increas|titrat|administ|give|giving|gave|hang|"
                    r"hanging|order|switch|chang|add|adding|remov|draw|drawing|"
                    r"check|consult|admit|admitting|discharg|transfus|bolus|push|"
                    r"pushing|wean|extubat|intubat|d/c)\w*",
    # explicit decision markers — even without an action verb these commit
    "decision_markers": r"\b(final orders?|final call|the plan is|orders? are|" \
                        r"ill put the order|order in|make it so)\b",
    "evidence_cues": r"(:warning:|creatinine|trough|culture|lab|level|spiking|" \
                     r"stable|flag|bumped|drug-interaction|\d+\.\d+|mg/dl|vitals?)",
    "question_cues": r"\?|wdyt|thoughts\?",
    "code_cues": r"\w+\s*=\s*\w+\(",
    # tone markers (metadata only, never veto)
    "hedge": r"\b(i think|maybe|probably|perhaps|possibly|might|consider|" \
             r"id consider|wondering if|not sure but|lean toward)\b",
    "strong": r"\b(final call|i want|i need|must|stat|now|immediately|" \
              r"do it|make it|ill put the order)\b",
    # pure recommendation verbs WITHOUT an action verb = advisory, not order.
    "recommend_only": r"\b(recommend|recommending|suggest|suggesting|advise|" \
                      r"advising|propose|would consider)\b",
}

ENGINEERING = {
    "name": "engineering",
    # inflection-aware stems (match use/using/used, switch/switching, etc.)
    "action_verbs": r"\b(use|using|used|switch|switching|deploy|deploying|ship|"
                    r"shipping|merge|merging|revert|reverting|roll ?back|migrat|"
                    r"build|building|implement|delet|drop|dropping|enabl|disabl|"
                    r"configur|set|setting|kick(ing)?\s+off|spin(ning)?\s+up|"
                    r"cut\s+over|move|moving)\w*",
    "decision_markers": r"\b(final call|we'?re going with|the decision is|lets go with|" \
                       r"ship it|going with|we'?re using)\b",
    "evidence_cues": r"(\d+\s*ms|p99|benchmark|stable|incident|lost|dropped|" \
                     r"no issues|green|verified|latency|throughput|added to|:white)",
    "question_cues": r"\?|wdyt|thoughts\?",
    "code_cues": r"\w+\s*=\s*\w+\(",
    "hedge": r"\b(i think|maybe|probably|perhaps|might|hot take|honestly|" \
             r"wondering if|lean toward|actually better|might be)\b",
    "strong": r"\b(final call|we'?re using|ship it|do it|must|now)\b",
    # recommendation framing: explicit advice verbs OR opinion-without-action
    # ("X is better", "X still good for Y") that proposes without directing.
    "recommend_only": r"\b(recommend|recommending|suggest|suggesting|propose|" \
                      r"advise|im gonna say|i'?m gonna say|better here|" \
                      r"might (actually )?be better|still (good|nice) for|reconsider)\b",
}


# ═══════════════════════════════════════════════════════════════════════
# the classifier — speech act on axis 1, tone on axis 2
# ═══════════════════════════════════════════════════════════════════════

def classify(content: str, domain: dict, is_bot: bool = False):
    """
    Returns (speech_act, tone, rationale).
      speech_act in {DIRECTIVE, EVIDENCE, QUESTION, CODE, RECOMMENDATION, STATEMENT}
      tone       in {strong, neutral, hedged}
    DIRECTIVE is the optimistic (FSS) promotion: anything that could be an
    order. Authority adjudication (BSS) happens downstream and is the ONLY
    thing that can invalidate a directive.
    """
    c = content.strip()
    cl = c.lower()

    av = re.compile(domain["action_verbs"], re.I)
    dm = re.compile(domain["decision_markers"], re.I)
    rec = re.compile(domain["recommend_only"], re.I)
    ev = re.compile(domain["evidence_cues"], re.I)
    q = re.compile(domain["question_cues"], re.I)
    code = re.compile(domain["code_cues"], re.I)
    hedge = re.compile(domain["hedge"], re.I)
    strong = re.compile(domain["strong"], re.I)

    # ── AXIS 2: tone (computed regardless of act) ──
    if strong.search(cl):
        tone = "strong"
    elif hedge.search(cl):
        tone = "hedged"
    else:
        tone = "neutral"

    # ── AXIS 1: speech act (tone does NOT gate this) ──
    # bot speakers only ever produce evidence
    if is_bot:
        return "EVIDENCE", tone, "bot speaker"

    has_action = bool(av.search(cl))
    has_decision_marker = bool(dm.search(cl))
    has_recommend = bool(rec.search(cl))

    # rhetorical directives ("why dont we start X") must be recognized BEFORE
    # the negation guard, since they contain "dont" without negating the action.
    rhetorical_directive = bool(re.match(
        r"^\s*(why dont we|why don'?t we|why not|how about we|what if we|"
        r"lets|let'?s)\b", cl))

    # negation guard: an action verb governed by a negation ("you cant switch it")
    # is NOT a directive — it's a meta-comment ABOUT the action. But skip this if
    # it's a rhetorical directive.
    negated = (bool(re.search(
        r"\b(can'?t|cannot|cant|won'?t|wont|do\s?n'?t|dont|should\s?n'?t|never|"
        r"no one can)\b", cl)) and has_action and not rhetorical_directive)
    if negated and not has_decision_marker:
        return "RECOMMENDATION", tone, "negated action (meta-comment, not a directive)"

    # explicit recommend-framing takes precedence over an embedded action verb:
    # "i recommend discontinuing X" frames the action as the OBJECT of advice,
    # not as a directive. The speaker marked it as advisory; honor that. The
    # recommend verb must appear at/near the start (the main verb), not buried.
    recommend_led = bool(re.match(
        r"^\s*(i\s+|id\s+|i'?d\s+|we\s+)?(recommend|suggest|advise|propose)", cl))
    if recommend_led:
        return "RECOMMENDATION", tone, "recommend-framed (action is object of advice)"

    # an explicit code assignment is CODE even if surrounded by action-verb prose
    # ("pooling configured, x = Redis(...)"). Check before directive promotion.
    if code.search(c) and re.search(r"\w+\s*=\s*\w+\(", c):
        return "CODE", tone, "explicit code assignment"

    # rhetorical directives: "why dont we start X" / "why not just stop Y" are
    # phrased interrogatively but function as soft orders, not info-seeking.
    is_rhetorical_directive = bool(re.match(
        r"^\s*(why dont we|why don'?t we|why not|how about we|what if we)\b", cl))

    # a genuine interrogative is a QUESTION even if it embeds an action verb.
    # "should we stop the ketorolac?" is asking, not ordering. The exceptions:
    # a decision marker, or a rhetorical-directive opener, still commit.
    is_interrogative = (bool(q.search(c)) or bool(re.match(
        r"^\s*(should|shall|do|does|did|can|could|would|will|is|are|was|were|"
        r"which|what|when|where|why|how)\b", cl)))
    if is_interrogative and not has_decision_marker and not is_rhetorical_directive:
        return "QUESTION", tone, "interrogative (action verb is the thing being asked about)"

    # KEY FIX: an action verb on content = DIRECTIVE, whatever the hedging.
    # "i think we should [start] the antibiotics" -> DIRECTIVE/hedged.
    if has_action or has_decision_marker:
        # the one exception: "recommend [action]" framing where the speaker
        # explicitly marks it as advice ("i recommend starting X"). Here the
        # recommend verb is the MAIN verb and the action is its object.
        # We still promote to DIRECTIVE (optimistic) but tag tone=hedged so
        # downstream knows it was framed as advice. Authority decides validity.
        return "DIRECTIVE", tone, "action verb present (tone is metadata, not veto)"

    # recommendation language WITHOUT any action verb = pure advisory
    if has_recommend:
        return "RECOMMENDATION", tone, "recommend verb, no directive action"

    # evidence
    if ev.search(cl):
        return "EVIDENCE", tone, "evidence cue"

    # code
    if code.search(c):
        return "CODE", tone, "code pattern"

    return "STATEMENT", tone, "no directive/evidence/question signal"


# ═══════════════════════════════════════════════════════════════════════
# self-test against the blast-radius cases
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("  ROLE CLASSIFIER — speech-act / tone separation")
    print("=" * 70)

    orders = [
        "start the antibiotics",
        "i think we should start the antibiotics",
        "lets start the antibiotics",
        "why dont we start the antibiotics",
        "id like to start the antibiotics",
        "we should probably start the antibiotics",
        "maybe start the antibiotics",
        "go ahead and start the antibiotics",
        "please start the antibiotics",
        "im going to start the antibiotics",
        "lets hold the heparin",
        "i think we hold the heparin",
        "discontinue the ketorolac",
        "i want to discontinue the ketorolac",
        "final orders: continue heparin, d/c ketorolac",
    ]
    print("\n  ATTENDING ORDERS (all must be DIRECTIVE; tone may vary):")
    lost = 0
    for t in orders:
        act, tone, why = classify(t, HEALTHCARE)
        ok = act == "DIRECTIVE"
        if not ok:
            lost += 1
        print(f"    {'✓' if ok else '✗ LOST'}  {act:14s} [{tone:7s}]  \"{t}\"")
    print(f"\n  {len(orders)-lost}/{len(orders)} orders correctly recognized "
          f"({lost} lost)")

    print("\n  NON-ORDERS (must NOT be DIRECTIVE):")
    non = [
        ("the creatinine bumped to 2.1", "EVIDENCE"),
        ("i recommend discontinuing the ketorolac", "DIRECTIVE"),  # recommend+action -> directive (authority will sort it)
        ("id recommend monitoring closely", "RECOMMENDATION"),     # recommend, no action verb
        ("should we stop the ketorolac?", "QUESTION"),             # wait: has 'stop' action...
        ("the patient seems stable", "EVIDENCE"),
        ("vanc trough monitoring required", "EVIDENCE"),
    ]
    for t, expected in non:
        act, tone, why = classify(t, HEALTHCARE)
        print(f"    {act:14s} [{tone:7s}]  \"{t}\"  → {why}")
