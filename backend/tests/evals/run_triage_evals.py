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
        "expected_event": None,
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
    # ── RECALL + PRECISION PAIR — director broadcasts, same sender ────────
    # These two are a contrasting pair drawn from REAL email. Both are from
    # the PYP director and both went to all staff. The discriminator is NOT
    # the sender — it's whether the broadcast hands each teacher a concrete,
    # dated task. The first was missed in production; the second must stay
    # ignored so the fix doesn't just flag everything Kimberly sends.
    {
        "id": "eval_director_meeting_broadcast",
        "subject": "Reuniones de seguimiento",
        "snippet": "Buenos días, compañeros: Me gustaría reunirme con cada uno de ustedes entre el 8 y el 17 de junio. Les agradezco ingresar a mi calendario para reservar un espacio de 40 minutos.",
        "body": (
            "Buenos días, compañeros:\n\n"
            "Me gustaría reunirme con cada uno de ustedes durante el período "
            "comprendido entre el 8 y el 17 de junio. Les agradezco ingresar a "
            "mi calendario para reservar un espacio de 40 minutos en el horario "
            "que mejor les convenga.\n\n"
            "Durante esta reunión de seguimiento abordaremos seguimiento de "
            "estudiantes y familias, retroalimentación de Dirección, y "
            "necesidades y proyecciones para el próximo semestre."
        ),
        "sender": "Kimberly María Fonseca <kimberly.fonseca@goldenvalley.ed.cr>",
        "to": "Personal Docente <staff@goldenvalley.ed.cr>",
        "cc": "",
        "expected_category": "action_required",
        "description": "Director broadcast, but assigns each teacher a dated concrete task (book a 40-min slot). The real miss.",
    },
    {
        "id": "eval_director_encouragement_broadcast",
        "subject": "Viralizar lo bueno: multiplicando liderazgos positivos",
        "snippet": "Estimados docentes: los invito a enfocar nuestras acciones en viralizar lo bueno, reconociendo y reforzando las buenas acciones y liderazgos positivos de los estudiantes.",
        "body": (
            "Estimados docentes:\n\n"
            "En el cierre de este semestre, los invito a enfocar nuestras "
            "acciones durante las próximas tres semanas en viralizar lo bueno: "
            "reconocer, visibilizar y reforzar las buenas acciones, actitudes y "
            "liderazgos positivos de nuestros estudiantes. Les invito a "
            "intencionar espacios cotidianos de aula para destacar lo bueno."
        ),
        "sender": "Kimberly María Fonseca <kimberly.fonseca@goldenvalley.ed.cr>",
        "to": "Personal Docente <staff@goldenvalley.ed.cr>",
        "cc": "",
        "expected_category": "ignore",
        "description": "Same director, broadcast, but pure encouragement with no concrete deliverable or deadline. Precision guard for the case above.",
    },
    # ── RECALL + PRECISION PAIR #2 — gratitude opener, real Kim emails ────
    # Overfitting guard. BOTH open with a long paragraph of thanks, and the
    # IGNORE one even contains "cada uno de ustedes" — so neither warmth nor
    # that phrase can be the trigger. The only difference is whether the body
    # hands me dated deliverables. Keying on phrasing would fail both.
    {
        "id": "eval_kim_cierre_ciclo",
        "subject": "Cierre de ciclo — fechas y lineamientos",
        "snippet": "Querido equipo, gracias por su compromiso. A continuación les comparto las fechas para el cierre de ciclo: cierre de unidad en Toddle (08 de junio), cierre de notas (05 de junio), entrega de reportes (16-17 de junio).",
        "body": (
            "Querido equipo, quiero comenzar expresando mi agradecimiento "
            "profundo por el compromiso y la dedicación que han demostrado en "
            "todo momento. A continuación les comparto las fechas y lineamientos "
            "importantes para el cierre de ciclo:\n\n"
            "Cierre de Unidad en Toddle — fecha límite 08 de junio, con las "
            "reflexiones de estudiantes y docentes completadas.\n"
            "Cierre y revisión de notas, conducta y comentarios — fecha límite "
            "05 de junio. Los comentarios deben estar listos para revisión el "
            "05 de junio.\n"
            "Revisión de notas con Santiago Montero — del 08 al 12 de junio con "
            "cita previa.\n"
            "Perfiles de Salida Grupos B — entrega del 08 al 12 de junio, en la "
            "carpeta correspondiente.\n"
            "Entrega de notas y reportes — presencial 16-17 de junio; recuerden "
            "enviar a las familias el link para que se anoten.\n"
            "Retiro de pertenencias — todos los estudiantes deben llevarse sus "
            "pertenencias a más tardar el jueves 11 de junio."
        ),
        "sender": "Kimberly María Fonseca <kimberly.fonseca@goldenvalley.ed.cr>",
        "to": "Personal Docente <staff@goldenvalley.ed.cr>",
        "cc": "",
        "expected_category": "action_required",
        "description": "Long gratitude opener, then a dense list of dated deliverables that are mine to do. Must flag despite the warm tone.",
    },
    {
        "id": "eval_kim_pyp_thankyou",
        "subject": "Gracias equipo — cierre del proceso PYP",
        "snippet": "Querido equipo: hoy culminamos un proceso significativo para nuestro programa PYP y quiero agradecerles de corazón a cada uno de ustedes. En aproximadamente un mes contaremos con el informe oficial.",
        "body": (
            "Querido equipo: hoy culminamos un proceso sumamente significativo "
            "para nuestro programa PYP, y quiero detenerme un momento para "
            "agradecerles de corazón a cada uno de ustedes. Gracias por su "
            "entrega, su compromiso constante y el cariño que ponen en cada "
            "detalle de su trabajo. La retroalimentación que recibimos fue muy "
            "positiva y resaltó que somos una comunidad sólida, un equipo unido "
            "y profesional. En aproximadamente un mes contaremos con el informe "
            "oficial. Por ahora, quiero que se queden con esto: me siento "
            "profundamente orgullosa de ser parte de este equipo. Sigamos "
            "construyendo juntos. ¡Lo mejor aún está por venir!"
        ),
        "sender": "Kimberly María Fonseca <kimberly.fonseca@goldenvalley.ed.cr>",
        "to": "Personal Docente <staff@goldenvalley.ed.cr>",
        "cc": "",
        "expected_category": "ignore",
        "description": "Pure gratitude/celebration — contains 'cada uno de ustedes' but nothing to deliver. The phrasing-overfit guard.",
    },
    # ── RECALL — broadcast form reminder IS a task ────────────────────────
    # Phrased as a question to all staff, but "complete the end-of-period
    # form" is a concrete deliverable that falls on me. The old label here
    # was `ignore` under the blunt "broadcast = not mine" rule we removed.
    {
        "id": "eval_staff_form",
        "subject": "Recordatorio formulario",
        "snippet": "Estimados docentes, ¿ya completaron el formulario de fin de período? Gracias.",
        "body": "Estimados docentes, ¿ya completaron el formulario de fin de período? Gracias.",
        "sender": "Coordinación <coordinacion@goldenvalley.ed.cr>",
        "to": "Personal Docente <staff@goldenvalley.ed.cr>",
        "cc": "",
        "expected_category": "action_required",
        "description": "Broadcast reminder to complete a form — a deliverable that's mine, so action_required despite the collective greeting.",
    },
    # ── PRECISION TRAP — broadcast question with NO deliverable ────────────
    # The boundary partner to eval_staff_form: a question to all staff that
    # asks for nothing concrete back. Guards against flagging every broadcast
    # question now that some of them (forms) legitimately flag.
    {
        "id": "eval_staff_checkin",
        "subject": "¿Cómo les fue esta semana?",
        "snippet": "Estimados docentes, ¿cómo se sintieron con el cierre de la semana? Cualquier comentario es bienvenido. Saludos.",
        "body": "Estimados docentes, ¿cómo se sintieron con el cierre de la semana? Cualquier comentario es bienvenido, pero no es obligatorio. Saludos.",
        "sender": "Coordinación <coordinacion@goldenvalley.ed.cr>",
        "to": "Personal Docente <staff@goldenvalley.ed.cr>",
        "cc": "",
        "expected_category": "ignore",
        "description": "Broadcast check-in question, optional and with nothing to deliver — must stay ignore.",
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
    # ── REAL INBOX (2026-06-04 dual-model comparison) — Small-3 missed these ──
    {
        "id": "eval_kim_meeting_reserve",
        "subject": "Reunión de cierre de semestre con Dirección",
        "snippet": "Buenos días, compañeros: Me gustaría reunirme con cada uno de ustedes durante el período comprendido entre el 8 y el 17 de junio. Les agradezco ingresar a mi calendario para reservar un espacio de 40 minutos.",
        "body": "Buenos días, compañeros: Espero que se encuentren muy bien. Me gustaría reunirme con cada uno de ustedes durante el período comprendido entre el 8 y el 17 de junio. Les agradezco ingresar a mi calendario para reservar un espacio de 40 minutos en el horario que mejor les convenga. Durante esta reunión de seguimiento abordaremos: seguimiento de estudiantes, retroalimentación de Dirección, proyecciones para el próximo semestre. Con gratitud, Kim",
        "sender": '"Kimberly María Fonseca Arguello" <kimberly.fonseca@goldenvalley.ed.cr>',
        "to": "GVS Montessori Teachers <montessoriteachers@goldenvalley.ed.cr>, GVS Primary Teachers <primaryteachers@goldenvalley.ed.cr>",
        "cc": "",
        "expected_category": "action_required",
        "description": "Director broadcast that hands each teacher a dated task (reserve a 40-min slot, Jun 8-17). Collective greeting, but the deliverable is mine. Small-3 ignored it; reasoning caught it.",
    },
    {
        "id": "eval_fabiola_exam_count",
        "subject": "Cantidad de exámenes a imprimir",
        "snippet": "Buenas tardes, Les adjunto el documento para que por favor anoten la cantidad de exámenes que necesitan. Cualquier consulta con gusto.",
        "body": "Buenas tardes, Espero que todos se encuentren bien. Les adjunto el documento para que por favor anoten la cantidad de exámenes que necesitan. Cualquier consulta con gusto. Saludos,",
        "sender": "Fabiola Jimenez <fabiola.jimenez@goldenvalley.ed.cr>",
        "to": "GVS Secondary Teachers <secondaryteachers@goldenvalley.ed.cr>",
        "cc": '"Carolina de los Ángeles Marín Siles" <carolina.marin@goldenvalley.ed.cr>, "Kimberly María Fonseca Arguello" <kimberly.fonseca@goldenvalley.ed.cr>',
        "expected_category": "action_required",
        "description": "Key sender (exam coordinator) broadcast with a concrete deliverable (note exam counts in the doc). Teacher prefers recall here even when not giving exams this cycle. Small-3 missed it.",
    },
    {
        "id": "eval_carolina_homeroom_form",
        "subject": "Fwd: Estado de proyectores y parlantes en aulas",
        "snippet": "Buenas tardes. Por favor 8A1, 8A2, 11A1 llenar el form. Saludos.",
        "body": "Buenas tardes. Por favor 8A1, 8A2, 11A1 llenar el form. Saludos. ---------- Forwarded message --------- De: Carolina de los Ángeles Marín Siles <carolina.marin@goldenvalley.ed.cr> Buenos días: El presente formulario tiene como objetivo recopilar información sobre el estado y funcionamiento de los proyectores en las aulas. Por favor, solicitamos que *un docente homeroom por grupo* complete el formulario, con el fin de consolidar la información y trasladarla a los departamentos de IT y Operaciones. Agradecemos completarlo a la brevedad posible. Form https://forms.gle/aVdRjsa1rXFuyzaa8",
        "sender": '"Carolina de los Ángeles Marín Siles" <carolina.marin@goldenvalley.ed.cr>',
        "to": "GVS Secondary Teachers <secondaryteachers@goldenvalley.ed.cr>",
        "cc": "",
        "expected_category": "ignore",
        "description": "PRECISION TRAP: director form scoped to 'un docente homeroom por grupo' for 8A1/8A2/11A1. Teacher is homeroom of 9A2 ONLY (and doesn't teach 11), so NOT his task. Needs the teaching≠homeroom discriminator; without it the model over-flags because it teaches 8A1.",
    },
    # ── EVENT — calendar invite where the teacher is a named guest → shown ──
    {
        "id": "eval_event_calendar_invite",
        "subject": "Updated invitation: Reunión secundaria @ Fri Jun 5, 2026 12pm - 12:45pm",
        "snippet": "Reunión secundaria — Friday Jun 5, 2026 12pm–12:45pm. Nos vemos en la biblioteca. Join with Google Meet…",
        "body": "This event has been updated\nChanged: time\n\nReunión secundaria\nFriday Jun 5, 2026 ⋅ 12pm – 12:45pm\nCentral Standard Time - Costa Rica\n\nJoin with Google Meet\nhttps://meet.google.com/ixh-zdnb-ifk\n\nHola a todos, nos gustaría tener un espacio con ustedes. Nos vemos en la biblioteca. Un abrazo,\n\nOrganizer: Priscilla Noguera rh@goldenvalley.ed.cr\nGuests: Priscilla Noguera - organizer, Esteban Villalobos, Stefan Linge, Camilo Infante, Michael Roberts, Bryan Castillo\nView event: https://calendar.google.com/calendar/event?action=VIEW&eid=NWRwcTQzcGgydTc2ODE1anE0Y2FrNHBpZG0gY2FtaWxvLmluZmFudGU",
        "sender": "Priscilla Noguera <rh@goldenvalley.ed.cr>",
        "to": CAMILO,
        "cc": "",
        "expected_category": "action_required",
        "expected_event": {"visibility": "shown"},
        "description": "Google Calendar invite (an update). Camilo is a named guest → event shown. Physical room 'biblioteca' is in the body alongside a Meet link; an eid is present.",
    },
    # ── EVENT — school-wide assembly, no personal role → hidden ────────────
    {
        "id": "eval_event_schoolwide_assembly",
        "subject": "Asamblea general este viernes",
        "snippet": "Estimados docentes, este viernes a las 9:00am tendremos asamblea general en el gimnasio.",
        "body": "Estimados docentes, les recordamos que este viernes 6 de junio a las 9:00am tendremos la asamblea general de fin de semestre en el gimnasio. Saludos.",
        "sender": "Comunicaciones <comunicaciones@goldenvalley.ed.cr>",
        "to": "Personal Docente <staff@goldenvalley.ed.cr>",
        "cc": "",
        "expected_category": "ignore",
        "expected_event": {"visibility": "hidden"},
        "description": "A dated school-wide assembly: broadcast, no role for her → event hidden (and category ignore). Discriminates relevance from mere date-presence.",
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

    # ── Event extraction / visibility sub-eval ────────────────────────────
    # Runs over the same batch results. A case opts in with "expected_event":
    #   None                     → expect NO event extracted
    #   {"visibility": "shown"}  → expect an event with that visibility
    event_cases = [case for case in EVAL_CASES if "expected_event" in case]
    event_passed = 0
    event_failures: list[tuple[dict, str]] = []

    if event_cases:
        print("\n" + "-" * 70)
        print("📅 EVENT EXTRACTION / VISIBILITY")
        print("-" * 70)
        for case in event_cases:
            event = result_map.get(case["id"], {}).get("event")
            expected = case["expected_event"]
            if expected is None:
                ok = not event
                got_desc = "event extracted" if event else "no event"
                want_desc = "no event"
            else:
                got_visibility = event.get("visibility") if event else "(no event)"
                ok = bool(event) and got_visibility == expected["visibility"]
                got_desc = got_visibility
                want_desc = expected["visibility"]

            if ok:
                event_passed += 1
                print(f'  ✅ {case["id"]:30s} → {got_desc}')
            else:
                print(f'  ❌ {case["id"]:30s} → {got_desc}  (expected {want_desc})')
                event_failures.append((case, str(got_desc)))

        print(f"\n  events: {event_passed}/{len(event_cases)} passed")

    total = len(EVAL_CASES)
    accuracy = passed / total * 100 if total else 0

    print("\n" + "=" * 70)
    print(f"📊 RESULTS: category {passed}/{total} ({accuracy:.0f}%)"
          f" · events {event_passed}/{len(event_cases)}")
    print("=" * 70)

    if failures:
        print("\n❌ CATEGORY FAILURES:")
        for case, got_cat in failures:
            print(f'  • {case["id"]} — {case["description"]}')
            print(f'    expected {case["expected_category"]}, got {got_cat}')
        print()

    if event_failures:
        print("\n❌ EVENT FAILURES:")
        for case, got_desc in event_failures:
            print(f'  • {case["id"]} — {case["description"]}')
            print(f'    expected {case["expected_event"]}, got {got_desc}')
        print()

    return 0 if not failures and not event_failures else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true", help="show case descriptions")
    args = parser.parse_args()
    sys.exit(asyncio.run(run_all_evals(verbose=args.verbose)))
