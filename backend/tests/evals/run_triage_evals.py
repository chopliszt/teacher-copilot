#!/usr/bin/env python3
"""
Triage Evals — Accuracy tests for the email-triage classifier.

Runs realistic emails through the exact same Mistral prompt used in
production (prompts/email_triage.py → triage_batch) and checks whether the
returned category matches what we expect.

WHY THIS LIVES OUTSIDE pytest:
  triage_batch hits the live Mistral API — it is non-deterministic, needs
  MISTRAL_API_KEY, and costs money. These evals measure *prompt quality*,
  not code correctness, so they are run on demand (or nightly), not in the
  normal `pytest tests/` unit run.

HOW TO GROW THIS SET:
  Every time a real email is mis-triaged, add it here as a labeled case.
  The set should grow from actual misses so the prompt can't silently
  regress on them again. The first case below is exactly that — an HR
  email that was wrongly ignored because it asked a question with no
  imperative verb.

Usage:
    python -m tests.evals.run_triage_evals            # run all evals
    python -m tests.evals.run_triage_evals --verbose  # show every result
"""

import argparse
import asyncio
import os
import sys

# Ensure backend module is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Load .env so MISTRAL_API_KEY is available outside of FastAPI
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from prompts.email_triage import triage_batch  # noqa: E402

CAMILO = "Camilo Infante <camilo.infante@goldenvalley.ed.cr>"

# ── Eval cases ────────────────────────────────────────────────────────────────
#
# Each case is a normal triage input (id, subject, snippet, body, sender, to,
# cc) plus an expected_category and a human description. The set is deliberately
# balanced: RECALL cases the old verb-allowlist missed (questions to me), and
# PRECISION traps that must stay `ignore` so we don't just flag every question.

EVAL_CASES: list[dict] = [
    # ── RECALL — the real miss that started this ──────────────────────────
    {
        "id": "eval_hr_question",
        "subject": "Re: Información del comité",
        "snippet": "Hola Camilo, muchas gracias por la información. ¿Cómo sería la reestructuración del comité? Feliz fin de semana. Un abrazo,",
        "body": "Hola Camilo, muchas gracias por la información.\n\n¿Cómo sería la reestructuración del comité?\n\nFeliz fin de semana.\n\nUn abrazo,",
        "sender": "Recursos Humanos <hr@goldenvalley.ed.cr>",
        "to": CAMILO,
        "cc": "",
        "expected_category": "action_required",
        "description": "Addressed to me + a direct question, no imperative verb. The original miss.",
    },
    # ── RECALL — second-person question from a known collaborator ─────────
    {
        "id": "eval_minute_opinion",
        "subject": "Minuta reunión 9°",
        "snippet": "Hola Camilo, ¿qué te pareció la minuta de la reunión de 9°? Quería saber tu opinión.",
        "body": "Hola Camilo, ¿qué te pareció la minuta de la reunión de 9°? Quería saber tu opinión antes de cerrarla.",
        "sender": "Michael Roberts <michael.roberts@goldenvalley.ed.cr>",
        "to": CAMILO,
        "cc": "",
        "expected_category": "action_required",
        "description": "Personal question expecting my opinion — ask without a command verb.",
    },
    # ── RECALL — director imperative ──────────────────────────────────────
    {
        "id": "eval_director_grades",
        "subject": "Notas 9A2",
        "snippet": "Camilo, por favor envíame las notas de 9A2 antes del viernes.",
        "body": "Camilo, por favor envíame las notas de 9A2 antes del viernes. Gracias.",
        "sender": "Carolina Marín <carolina.marin@goldenvalley.ed.cr>",
        "to": CAMILO,
        "cc": "",
        "expected_category": "action_required",
        "description": "Director with a direct imperative to me.",
    },
    # ── RECALL — substitute coordinator cover request (question) ──────────
    {
        "id": "eval_fabiola_cover",
        "subject": "Reemplazo 8A1",
        "snippet": "Camilo, ¿podés cubrir la clase de 8A1 mañana a las 10? Gracias.",
        "body": "Camilo, ¿podés cubrir la clase de 8A1 mañana a las 10? Gracias.",
        "sender": "Fabiola Jiménez <fabiola.jimenez@goldenvalley.ed.cr>",
        "to": CAMILO,
        "cc": "",
        "expected_category": "action_required",
        "description": "Cover request from the substitute coordinator, phrased as a question.",
    },
    # ── PRECISION TRAP — all-staff bulletin question (broadcast) ──────────
    {
        "id": "eval_staff_form",
        "subject": "Recordatorio formulario",
        "snippet": "Estimados docentes, ¿ya completaron el formulario de fin de período? Gracias.",
        "body": "Estimados docentes, ¿ya completaron el formulario de fin de período? Gracias.",
        "sender": "Coordinación <coordinacion@goldenvalley.ed.cr>",
        "to": "Personal Docente <staff@goldenvalley.ed.cr>",
        "cc": "",
        "expected_category": "ignore",
        "description": "A question, but broadcast to all staff — not addressed to me.",
    },
    # ── PRECISION TRAP — Cc-only, question aimed at someone else ──────────
    {
        "id": "eval_cc_budget",
        "subject": "Re: Presupuesto MYP",
        "snippet": "Hola Jose Daniel, ¿podrías confirmar el presupuesto para el próximo año? Gracias.",
        "body": "Hola Jose Daniel, ¿podrías confirmar el presupuesto para el próximo año? Gracias.",
        "sender": "Karla Aguilar <karla.aguilar@goldenvalley.ed.cr>",
        "to": "Jose Daniel Rojas <jose.rojas@goldenvalley.ed.cr>",
        "cc": CAMILO,
        "expected_category": "ignore",
        "description": "Question directed at Jose Daniel; I'm only on Cc.",
    },
    # ── PRECISION TRAP — addressed to me but no ask (pleasantry) ──────────
    {
        "id": "eval_thanks_no_ask",
        "subject": "Re: Información del comité",
        "snippet": "Gracias Camilo, con esto es suficiente. Feliz fin de semana, un abrazo.",
        "body": "Gracias Camilo, con esto es suficiente. No necesito nada más. Feliz fin de semana, un abrazo.",
        "sender": "Recursos Humanos <hr@goldenvalley.ed.cr>",
        "to": CAMILO,
        "cc": "",
        "expected_category": "ignore",
        "description": "Addressed to me, but a closing thank-you with no ask.",
    },
    # ── PRECISION TRAP — grade 11-12 broadcast, no ask ───────────────────
    {
        "id": "eval_grade11_info",
        "subject": "Salida pedagógica 11°",
        "snippet": "Estimados, los estudiantes de 11° tendrán salida pedagógica el viernes.",
        "body": "Estimados, los estudiantes de 11° tendrán salida pedagógica el viernes. Saludos.",
        "sender": "Coordinación Bachillerato <bachillerato@goldenvalley.ed.cr>",
        "to": "Personal Docente <staff@goldenvalley.ed.cr>",
        "cc": "",
        "expected_category": "ignore",
        "description": "Grade 11 info I don't teach, broadcast, no ask.",
    },
    # ── SANITY — absence forward still classified correctly ──────────────
    {
        "id": "eval_absence_fwd",
        "subject": "Fwd: Justificación",
        "snippet": "Student Excused Absence - 6B1 - Maria Gomez. Queda justificada su ausencia.",
        "body": "Estimado profesor, le informamos que la estudiante Maria Gomez del grupo 6B1 no asistirá hoy por motivos de salud. Student Excused Absence - 6B1 - Maria Gomez.",
        "sender": "secretaria@goldenvalley.ed.cr",
        "to": CAMILO,
        "cc": "",
        "expected_category": "absence",
        "description": "Forwarded absence justification — must extract student + group.",
    },
]


# ── Runner ────────────────────────────────────────────────────────────────────

async def run_all_evals(verbose: bool = False) -> int:
    print("\n" + "=" * 70)
    print("📧 EMAIL TRIAGE EVALS")
    print("=" * 70)

    if not os.getenv("MISTRAL_API_KEY"):
        print("\n❌ MISTRAL_API_KEY not set — cannot run live triage. Aborting.")
        return 1

    print(f"Running {len(EVAL_CASES)} cases through triage_batch (Mistral Small)...\n")

    # One batch call — same path production uses. Map results back by id.
    results = await triage_batch(EVAL_CASES)
    result_map = {r["id"]: r for r in results}

    passed = 0
    failures: list[tuple[dict, str]] = []

    for case in EVAL_CASES:
        got = result_map.get(case["id"], {})
        got_cat = got.get("category", "(missing)")
        expected = case["expected_category"]
        ok = got_cat == expected

        if ok:
            passed += 1
            print(f'  ✅ {case["id"]:24s} → {got_cat}')
        else:
            print(f'  ❌ {case["id"]:24s} → {got_cat}  (expected {expected})')
            failures.append((case, got_cat))

        if verbose:
            print(f'       {case["description"]}')

    total = len(EVAL_CASES)
    accuracy = passed / total * 100 if total else 0

    print("\n" + "=" * 70)
    print(f"📊 RESULTS: {passed}/{total} passed ({accuracy:.0f}% accuracy)")
    print("=" * 70)

    if failures:
        print("\n❌ FAILURES:")
        for case, got_cat in failures:
            print(f'  • {case["id"]} — {case["description"]}')
            print(f'    expected {case["expected_category"]}, got {got_cat}')
        print()

    return 0 if not failures else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true", help="show case descriptions")
    args = parser.parse_args()
    sys.exit(asyncio.run(run_all_evals(verbose=args.verbose)))
