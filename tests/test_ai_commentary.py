"""Tests of the AI commentary (T9), with a stand-in model: no network, no key, no cost."""

import csv
from datetime import datetime

import duckdb
import pytest

from src.ai import commentary as ai

SETTINGS = {
    "modele": "stand-in",
    "max_tokens": 700,
    "delai_entre_appels_s": 1.2,
    "tentatives_max": 3,
    "reflexion": "disabled",
}

KPIS = [
    # kpi, axe, pays, valeur, unite, seuil, statut_go, statut_epistemique, origine_donnees
    ("Croissance du secteur", "Marché", "DE", 4.21, "%", "≥ 2 %", "GO", "CALCUL", "SIMULE"),
    ("Indice prix relatif", "Prix", "DE", 101.5, "indice", None, "INFO", "CALCUL", "REEL"),
    ("Croissance du secteur", "Marché", "FR", 3.05, "%", None, "INFO", "CALCUL", "SIMULE"),
    ("Coût moyen au m²", "Réseau", "DE", 1480.0, "€/m²/an", None, "INFO", "CALCUL", "SIMULE"),
    (
        "Payback (scénario pessimiste) : Centre-ville",
        "Rentabilité",
        "DE",
        None,
        "mois",
        "≤ 36 mois",
        "NO-GO",
        "HYPOTHÈSE",
        "SIMULE",
    ),
    (
        "Payback (scénario central) : Centre-ville",
        "Rentabilité",
        "DE",
        66.1,
        "mois",
        None,
        "INFO",
        "HYPOTHÈSE",
        "SIMULE",
    ),
    (
        "Point mort par magasin : Centre-ville",
        "Rentabilité",
        "DE",
        525098.0,
        "€ de CA HT/an",
        None,
        "INFO",
        "CALCUL",
        "SIMULE",
    ),
]


@pytest.fixture
def warehouse(tmp_path):
    """A small warehouse with the four objects the commentary reads."""
    path = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE kpi_summary (kpi VARCHAR, axe VARCHAR, pays VARCHAR, valeur DOUBLE, "
        "unite VARCHAR, seuil VARCHAR, statut_go VARCHAR, statut_epistemique VARCHAR, "
        "origine_donnees VARCHAR)"
    )
    con.executemany("INSERT INTO kpi_summary VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", KPIS)
    con.execute(
        "CREATE TABLE dim_pays AS SELECT * FROM (VALUES ('DE', 'Allemagne'), "
        "('FR', 'France')) AS t(code_pays, nom_pays)"
    )
    con.execute(
        "CREATE TABLE city_scoring AS SELECT * FROM (VALUES ('Z001', 'München', 81.4, "
        "1, true, 'MIXTE'), ('Z002', 'Köln', 70.2, 2, false, 'MIXTE')) "
        "AS t(id_zone, ville, score, rang, est_prioritaire, origine_donnees)"
    )
    con.execute(
        "CREATE TABLE business_case AS SELECT * FROM (VALUES ('central'), "
        "('pessimiste')) AS t(scenario)"
    )
    con.close()
    return path


class StandIn:
    """Answers from a script, in order, and keeps every prompt it received."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts = []

    def generate(self, system, user):
        self.prompts.append(user)
        answer = self.answers.pop(0) if self.answers else "Texte sans chiffre."
        if isinstance(answer, Exception):  # e.g. a truncated answer
            raise answer
        return answer


def all_checks(*args, **kwargs):
    """(text, every check passed, problems): the reading of the tests written before the
    checks were split into three columns."""
    outcome = ai.comment(*args, **kwargs)
    ok = outcome.verifie and outcome.longueur_ok and outcome.formulations_ok
    return outcome.text, ok, outcome.probleme


def requests_of(path):
    con = duckdb.connect(str(path), read_only=True)
    try:
        return ai.build_requests(con)
    finally:
        con.close()


# -- Numbers ---------------------------------------------------------------------------
def test_numbers_are_read_in_french_and_english_notation():
    numbers = ai.extract_numbers("525 098 € de CA, 16,86 % d'occupation, 30.1 et 2027.")
    assert [(n.value, n.decimals) for n in numbers] == [
        (525098.0, 0),
        (16.86, 2),
        (30.1, 1),
        (2027.0, 0),
    ]


def test_identifiers_are_not_numbers():
    assert ai.extract_numbers("La zone Z001 et la tâche T7.") == []


def test_a_rounded_value_is_supported_an_invented_one_is_not():
    allowed = [16.86, 30.133]
    assert ai.unsupported_numbers("Coût de 16,9 %, impôt de 30 %.", allowed) == []
    assert ai.unsupported_numbers("Coût de 17,5 %.", allowed) == ["17,5"]


def test_a_scale_needs_its_word():
    allowed = [525098.0, 1234567.0]
    assert ai.unsupported_numbers("Point mort de 525 k€, soit 1,2 M€.", allowed) == []
    # Without a scale word, "1" is not accepted as 1.2 million rounded.
    assert ai.unsupported_numbers("Une seule ville, 1 sur la liste.", allowed) == ["1"]


def test_a_value_already_counted_in_millions_may_carry_the_word_million():
    """population_millions = 0,603 is rightly written "0,603 million d'habitants"."""
    assert ai.unsupported_numbers("Une population de 0,603 million.", [0.603]) == []
    assert ai.unsupported_numbers("Une population de 0,9 million.", [0.603]) == ["0,9"]


# -- Requests --------------------------------------------------------------------------
def test_every_page_and_filter_value_gets_one_request(warehouse):
    requests = requests_of(warehouse)
    keys = [(r.page, r.valeur_filtre) for r in requests]
    assert keys == [
        (ai.PAGE_SYNTHESIS, ai.ALL_VALUES),
        (ai.PAGE_MARKET, "Allemagne"),
        (ai.PAGE_MARKET, "France"),
        (ai.PAGE_CITIES, "München"),
        (ai.PAGE_CITIES, "Köln"),
        (ai.PAGE_BUSINESS, "central"),
        (ai.PAGE_BUSINESS, "pessimiste"),
        (ai.PAGE_SLIDE, ai.ALL_VALUES),
    ]


def test_a_market_request_only_sees_its_country_and_its_axes(warehouse):
    germany = next(r for r in requests_of(warehouse) if r.valeur_filtre == "Allemagne")
    text = "\n".join(germany.lines)
    assert "4,21 %" in text and "101,5 indice" in text
    # France only as the reference of the same KPI, with the gap computed by the code.
    assert "France : 3,05 % | écart à la France : +1,16 point" in text
    assert "1480" not in text  # Réseau axis
    assert "Payback" not in text  # Rentabilité axis


def test_a_business_request_only_sees_its_scenario_and_the_common_rows(warehouse):
    central = next(r for r in requests_of(warehouse) if r.valeur_filtre == "central")
    text = "\n".join(central.lines)
    assert "scénario central" in text and "Point mort" in text
    # The pessimistic scenario is only named as the one the payback threshold is judged on.
    assert "Payback (scénario pessimiste)" not in text
    assert "seuil : ≤ 36 mois, jugé sur le scénario pessimiste" in text


def test_a_missing_payback_is_said_not_reached(warehouse):
    # On the slide: the pessimistic page gives the team's sentence instead of its payback rows.
    assert ai.MISSING_PAYBACK in "\n".join(requests_of(warehouse)[-1].lines)


def test_the_slide_counts_the_verdicts(warehouse):
    synthesis = requests_of(warehouse)[-1]
    assert synthesis.page == ai.PAGE_SLIDE and synthesis.template == "synthese.md"
    # Searched, not indexed: the lines of the team decision, when there is one, come after.
    assert "- Verdicts des KPI à seuil : 1 GO, 1 NO-GO" in synthesis.lines


def test_the_synthesis_reads_the_team_decision_and_never_takes_it(warehouse):
    """README 4.2 has no rule to combine the criteria: the decision comes from the config,
    section `decision`, whatever its keys; the model only explains it."""
    config = ai.load_config()
    decision = {
        "verdict": "NO-GO en l'état, GO conditionnel",
        "conditions": ["environ 3 ETP", "CA/m² ≥ France + 2 %", "centre commercial"],
        "approvisionnement": {"hub": "Dordrecht"},
    }
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        without = ai.build_requests(con, {**config, "decision": None})[-1].lines
        with_decision = ai.build_requests(con, {**config, "decision": decision})[-1].lines
    finally:
        con.close()
    assert without[-1] == ai.DECISION_OPEN
    assert with_decision[-3:] == (
        "- décision retenue par l'équipe / verdict : NO-GO en l'état, GO conditionnel",
        "- décision retenue par l'équipe / conditions du GO : environ 3 ETP ; "
        "CA/m² ≥ France + 2 % ; centre commercial",
        "- décision retenue par l'équipe / approvisionnement / hub logistique : Dordrecht",
    )
    # The figures of the decision may then be quoted: they are part of the prompt.
    synthesis = ai.build_requests(
        con := duckdb.connect(str(warehouse), read_only=True), {**config, "decision": decision}
    )[-1]
    con.close()
    assert (
        ai.unsupported_numbers(
            "Il faut 3 ETP et +2 %.", ai.allowed_values(ai.user_prompt(synthesis))
        )
        == []
    )


def test_a_city_request_explains_how_to_read_the_notes(warehouse):
    """Without it, a distance note of 0 was read as a zero distance (Dresden, 12/11/2026)."""
    munich = next(r for r in requests_of(warehouse) if r.valeur_filtre == "München")
    text = "\n".join(munich.lines)
    assert "0 = la moins favorable des 2, jamais une valeur nulle" in text  # 2 cities here
    # Dortmund, note 100 on density, was said to have "une forte densité" (12/11/2026).
    assert "une note de densité élevée signifie une densité faible" in text
    assert "100 000 habitants" in text
    weights = ai.load_config()["city_scoring"]["poids"]
    assert all(f"{criterion} {weight}" in text for criterion, weight in weights.items())


# -- Generation ------------------------------------------------------------------------
def test_an_unsupported_number_triggers_one_regeneration(warehouse):
    request = next(r for r in requests_of(warehouse) if r.valeur_filtre == "Allemagne")
    model = StandIn("Croissance de 9,9 %.", "Croissance de 4,2 % (données simulées).")
    text, verified, _ = all_checks(model, request)
    assert verified and text == "Croissance de 4,2 % (données simulées)."
    assert len(model.prompts) == 2 and "9,9" in model.prompts[1]


def test_a_number_quoted_in_the_correction_does_not_become_allowed(warehouse):
    request = next(r for r in requests_of(warehouse) if r.valeur_filtre == "Allemagne")
    model = StandIn("Croissance de 9,9 %.", "Croissance de 9,9 %.")
    text, verified, problem = all_checks(model, request)
    assert not verified and text == "Croissance de 9,9 %."
    assert problem == "chiffres hors données : 9,9"


def test_an_empty_text_is_never_verified(warehouse):
    """No number at all passes a check of the numbers: emptiness is checked first."""
    request = next(r for r in requests_of(warehouse) if r.valeur_filtre == "Allemagne")
    text, verified, problem = all_checks(StandIn("", ""), request)
    assert (text, verified, problem) == ("", False, "texte vide")
    # A second, complete answer is accepted.
    text, verified, _ = all_checks(StandIn("", "Marché porteur."), request)
    assert verified and text == "Marché porteur."


def test_a_truncated_text_is_never_verified(warehouse):
    """A text cut at max_tokens may hold only right numbers: it is rejected all the same."""
    request = next(r for r in requests_of(warehouse) if r.valeur_filtre == "Allemagne")
    cut = ai.TruncatedAnswer("Croissance de 4,21 %, devant")
    text, verified, problem = all_checks(StandIn(cut, cut), request)
    assert (text, verified, problem) == ("Croissance de 4,21 %, devant", False, "texte tronqué")
    model = StandIn(cut, "Croissance de 4,21 % (données simulées).")
    text, verified, _ = all_checks(model, request)
    assert verified and model.prompts[0] == model.prompts[1]  # same prompt, no correction


def test_the_throttle_waits_between_calls_only():
    waits = []
    model = ai.Throttled(StandIn("a", "b", "c"), 1.2, waits.append)
    for _ in range(3):
        model.generate("system", "user")
    assert waits == [1.2, 1.2]


def test_run_writes_the_csv_and_the_table(warehouse, tmp_path):
    out = tmp_path / "ai_commentary.csv"
    synthesis = "Le marché croît.\nCroissance du secteur de 4,21 %."
    model = StandIn(synthesis)
    rows = ai.run(
        warehouse,
        out,
        model,
        SETTINGS,
        sleep=lambda _: None,
        now=lambda: datetime(2026, 11, 12, 15, 0, 0),
    )
    assert len(rows) == 8

    with out.open(encoding="utf-8", newline="") as file:
        written = list(csv.DictReader(file))
    assert list(written[0]) == ai.COLUMNS
    assert {"verifie", "longueur_ok", "formulations_ok"} <= set(ai.COLUMNS)
    assert written[0]["texte"] == synthesis  # the line breaks survive the CSV file
    assert {row["verifie"] for row in written} == {"true"}
    assert written[0]["date_generation"] == "2026-11-12T15:00:00"

    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        types = dict(con.execute(f"DESCRIBE {ai.TABLE}").fetchall()[i][:2] for i in range(6))
        types = dict(row[:2] for row in con.execute(f"DESCRIBE {ai.TABLE}").fetchall())
        assert types["verifie"] == "BOOLEAN" and types["date_generation"] == "TIMESTAMP"
        assert types["longueur_ok"] == "BOOLEAN" and types["formulations_ok"] == "BOOLEAN"
        assert con.execute(f"SELECT count(*) FROM {ai.TABLE}").fetchone()[0] == 8
    finally:
        con.close()


# -- Claude adapter --------------------------------------------------------------------
class FakeAnthropic:
    """Stands for anthropic.Anthropic: records the call, answers with a thinking block, which
    has no `text` attribute, then two text blocks."""

    calls = []
    stop_reason = "end_turn"

    def __init__(self, api_key, max_retries):
        self.init = {"api_key": api_key, "max_retries": max_retries}
        self.messages = self

    def create(self, **kwargs):
        FakeAnthropic.calls.append(kwargs)
        thinking = type("Block", (), {"type": "thinking", "thinking": "..."})()
        first = type("Block", (), {"type": "text", "text": "Marché en "})()
        second = type("Block", (), {"type": "text", "text": "croissance."})()
        content = [thinking, first, second]
        return type("Response", (), {"content": content, "stop_reason": self.stop_reason})()


def test_the_claude_adapter_sends_the_settings_and_joins_the_text_blocks(monkeypatch):
    import anthropic

    FakeAnthropic.calls = []
    monkeypatch.setattr(anthropic, "Anthropic", FakeAnthropic)
    model = ai.ClaudeModel("abc123", SETTINGS)
    assert model._client.init == {"api_key": "abc123", "max_retries": 3}
    assert model.generate("système", "demande") == "Marché en croissance."
    assert FakeAnthropic.calls == [
        {
            "model": "stand-in",
            "max_tokens": 700,
            "system": "système",
            "messages": [{"role": "user", "content": "demande"}],
            "thinking": {"type": "disabled"},
        }
    ]


def test_without_a_thinking_setting_nothing_is_sent(monkeypatch):
    import anthropic

    FakeAnthropic.calls = []
    monkeypatch.setattr(anthropic, "Anthropic", FakeAnthropic)
    ai.ClaudeModel("abc123", {**SETTINGS, "reflexion": None}).generate("s", "u")
    assert "thinking" not in FakeAnthropic.calls[0]


def test_an_answer_stopped_at_max_tokens_is_reported_as_truncated(monkeypatch):
    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", FakeAnthropic)
    monkeypatch.setattr(FakeAnthropic, "stop_reason", "max_tokens")
    with pytest.raises(ai.TruncatedAnswer) as answer:
        ai.ClaudeModel("abc123", SETTINGS).generate("s", "u")
    assert answer.value.text == "Marché en croissance."


def test_every_argument_sent_is_accepted_by_the_real_sdk(monkeypatch):
    """The stand-in above accepts anything: this test checks the call against the SDK itself.

    It catches an argument that the installed SDK no longer accepts (`temperature` was one),
    which the stand-in alone would let through until the first real call.
    """
    import inspect

    import anthropic

    accepted = set(inspect.signature(anthropic.Anthropic(api_key="x").messages.create).parameters)
    FakeAnthropic.calls = []
    monkeypatch.setattr(anthropic, "Anthropic", FakeAnthropic)
    ai.ClaudeModel("abc123", SETTINGS).generate("s", "u")
    assert set(FakeAnthropic.calls[0]) <= accepted


# -- Key -------------------------------------------------------------------------------
def test_the_key_is_read_from_a_dotenv_file_written_by_notepad(tmp_path, monkeypatch):
    monkeypatch.delenv(ai.API_KEY_NAME, raising=False)
    env = tmp_path / ".env"
    env.write_text(f"# commentaire\n{ai.API_KEY_NAME}=abc123\n", encoding="utf-8-sig")
    assert ai.load_api_key(env) == "abc123"


def test_a_missing_key_stops_with_a_clear_message(tmp_path, monkeypatch):
    monkeypatch.delenv(ai.API_KEY_NAME, raising=False)
    with pytest.raises(RuntimeError, match=ai.API_KEY_NAME):
        ai.load_api_key(tmp_path / ".env")


def test_the_slide_text_fits_its_limit_with_the_team_sentence(warehouse):
    """A synthesis without a limit was cut at max_tokens, after 816 words (12/11/2026). The
    team's sentence is added after the model's text: its words come off the model's limit."""
    slide = requests_of(warehouse)[-1]
    limit = ai.load_settings()["synthese_mots_max"]
    ending = ai.load_config()["decision"][ai.CONFIRMATION_KEY]
    assert slide.max_words == limit and slide.ending == ending
    assert slide.model_words == limit - ai.count_words(ending)
    # The model is asked for less than the limit it is checked against: it overshoots.
    assert slide.prompt_words < slide.model_words
    assert f"en {slide.prompt_words} mots au plus" in ai.user_prompt(slide)
    # The model never sees the sentence: it would rephrase it.
    assert "pilote" not in ai.user_prompt(slide)


def test_every_page_comment_is_short_and_starts_with_its_key_message(warehouse):
    """Two or three short sentences, the key message first (Jean-Li, 12/11/2026)."""
    limit = ai.load_settings()["commentaire_mots_max"]
    for request in requests_of(warehouse)[:-1]:
        prompt = ai.user_prompt(request)
        assert request.max_words == limit and f"{request.prompt_words} mots au plus" in prompt
        assert "deux ou trois phrases courtes au maximum" in prompt
        assert "La première phrase est le message clé, courte et sans aucun chiffre" in prompt


def test_a_tcam_is_written_as_a_yearly_rate():
    row = {
        "kpi": "Croissance du secteur (TCAM 2022-2025)",
        "axe": "Marché",
        "valeur": 3.89,
        "unite": "%",
        "seuil": "≥ 2 %",
        "statut_go": "GO",
        "statut_epistemique": "CALCUL",
        "origine_donnees": "SIMULE",
    }
    assert "valeur : 3,89 % par an" in ai.render_kpi(row)
    # A rate that is not a TCAM keeps its unit.
    assert "valeur : 14,94 % |" in ai.render_kpi(
        {**row, "kpi": "Coût d'occupation", "valeur": 14.94}
    )


DECISION = {
    "verdict": "NO-GO en l'état, GO conditionnel",
    "conditions": {"format": "Centre commercial", "nb_etp": 3.0, "ca_m2_min_vs_france": 1.02},
}


def add_sensitivity_view(path):
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE sensibilite_payback AS SELECT * FROM (VALUES "
        "('DE', 'pessimiste', 'Centre commercial', 3.0, 1.02, 5707.0, 35.5, '≤ 36 mois', 'GO', "
        "'SIMULE'), "
        "('DE', 'pessimiste', 'Centre commercial', 3.0, 1.00, 5595.0, 41.2, '≤ 36 mois', 'NO-GO', "
        "'SIMULE')) AS t(code_pays, scenario, format, nb_etp, ratio_ca_m2_vs_france, ca_m2_eur, "
        "payback_mois, seuil, statut_go, origine_donnees)"
    )
    con.close()


def test_the_team_condition_goes_to_the_slide_never_to_the_dashboard(warehouse):
    """The 35,5 months come from sensibilite_payback, on the row of the decision: a value the
    guard rail accepts, not the figure of a comment of the config. A condition for a GO is a
    recommendation: the slide has it, no page of the dashboard (teacher, 13/11/2026)."""
    add_sensitivity_view(warehouse)
    config = {**ai.load_config(), "decision": DECISION}
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        requests = ai.build_requests(con, config)
    finally:
        con.close()
    slide = requests[-1]
    condition = slide.lines[-1]
    assert "3 ETP" in condition and "France + 2 %" in condition
    assert "payback 35,5 mois" in condition and "verdict GO" in condition
    assert "41,2" not in condition  # the other row of the view is not the condition
    allowed = ai.allowed_values(ai.user_prompt(slide))
    assert ai.unsupported_numbers("GO possible à 3 ETP, France + 2 %, en 35,5 mois.", allowed) == []
    for request in requests[:-1]:
        assert not any("condition de l'équipe" in line for line in request.lines)


def test_without_a_decision_or_the_view_there_is_no_condition(warehouse):
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        assert ai.lifting_condition(con, DECISION) is None  # no sensitivity view here
        assert ai.lifting_condition(con, None) is None
    finally:
        con.close()


def test_another_layout_of_the_decision_gives_no_condition_and_no_crash(warehouse):
    add_sensitivity_view(warehouse)
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        for decision in ({"conditions": ["3 ETP", "centre commercial"]}, {"conditions": {}}, "GO"):
            assert ai.lifting_condition(con, decision) is None
    finally:
        con.close()


def test_a_city_gets_its_rank_on_each_note():
    """Dortmund, 2nd overall, was said to have a solid potential with a note of 6,4."""
    cities = [
        {"ville": "Berlin", "note_potentiel": 100.0, "note_loyer": 37.3},
        {"ville": "Dortmund", "note_potentiel": 6.4, "note_loyer": 90.4},
        {"ville": "Köln", "note_potentiel": 33.8, "note_loyer": 90.4},
    ]
    (line,) = ai.criterion_ranks(cities[1], cities)
    assert "note_potentiel rang 3 sur 3" in line  # the weakest potential of the three
    assert "note_loyer rang 1 sur 3" in line  # tied first: both have 90,4
    assert ai.criterion_ranks({"ville": "X"}, [{"ville": "X"}]) == ()  # no note, no line


# -- Dashboard: facts and gaps, no verdict (teacher, 13/11/2026) -------------------------
def test_the_dashboard_pages_get_positions_and_gaps_never_verdicts(warehouse):
    requests = requests_of(warehouse)
    for request in requests[:-1]:
        text = "\n".join(request.lines)
        assert "verdict" not in text and "est_prioritaire" not in text
    germany = next(r for r in requests if r.valeur_filtre == "Allemagne")
    assert "position : seuil respecté | écart au seuil : +2,21 points" in germany.lines[0]
    config = ai.load_config()
    config = {**config, "ia": {**config["ia"], "phrases_equipe": None}}
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        pessimistic = next(
            r for r in ai.build_requests(con, config) if r.valeur_filtre == "pessimiste"
        )
    finally:
        con.close()
    assert "position : seuil non respecté" in "\n".join(pessimistic.lines)
    # The slide keeps the verdicts.
    assert "verdict : NO-GO" in "\n".join(requests[-1].lines)


def test_a_scenario_without_threshold_points_to_the_one_it_is_judged_on():
    """The pessimistic page said "sans seuil fixé" for an occupancy cost (Jean-Li, 13/11/2026)."""
    rows = [
        {
            "kpi": "Coût d'occupation (scénario central) : Centre commercial",
            "pays": "DE",
            "seuil": "≤ 15 %",
        },
        {
            "kpi": "Coût d'occupation (scénario pessimiste) : Centre commercial",
            "pays": "DE",
            "seuil": None,
        },
    ]
    thresholds = ai.scenario_thresholds(rows)
    row = {
        **rows[1],
        "axe": "Rentabilité",
        "valeur": 17.92,
        "unite": "%",
        "statut_go": "INFO",
        "statut_epistemique": "CALCUL",
        "origine_donnees": "SIMULE",
    }
    line = ai.render_kpi(row, verdict=False, thresholds=thresholds)
    assert "seuil : ≤ 15 %, jugé sur le scénario central | écart au seuil : +2,92 points" in line


def test_the_business_pages_say_the_labels_are_formats(warehouse):
    for request in requests_of(warehouse):
        assert (ai.FORMATS_LINE in request.lines) == (request.page == ai.PAGE_BUSINESS)


def test_gaps_are_computed_by_the_code_in_the_unit_of_the_kpi():
    assert ai.gap(3.89, 2.0, "%") == "+1,89 point"
    assert ai.gap(13.97, 24.03, "%") == "\u221210,06 points"
    assert ai.gap(100.85, 100.0, "indice") == "+0,85 point d'indice"
    assert ai.gap(93.9, 36.0, "mois") == "+57,9 mois"
    assert ai.gap(4.26, 4.26, "%") == "aucun écart"
    assert ai.threshold_bound("≥ 66.91 %") == 66.91 and ai.threshold_bound("95 à 110") is None


# -- Thousands, words, forbidden phrases (Jean-Li, 13/11/2026) ---------------------------
def test_large_numbers_get_a_thousands_separator_years_do_not():
    nbsp = "\u00a0"
    assert ai.format_value(565010.0) == f"565{nbsp}010"
    assert ai.format_value(1234567.25) == f"1{nbsp}234{nbsp}567,25"
    assert ai.format_value(5707.0) == "5707" and ai.format_value(66.1) == "66,1"
    assert ai.normalize_numbers("Point mort de 565010 € en 2027, 14,94 %.") == (
        f"Point mort de 565{nbsp}010 € en 2027, 14,94 %."
    )
    # The grouped number is still read as one number by the guard rail.
    assert ai.unsupported_numbers(ai.normalize_numbers("565010 €"), [565010.0]) == []


def test_words_are_counted_a_number_being_one_word():
    assert ai.count_words("Le point mort atteint 565 010 € de CA, soit 14,94 %.") == 9


def test_a_text_over_its_limit_is_regenerated(warehouse):
    request = next(r for r in requests_of(warehouse) if r.valeur_filtre == "Allemagne")
    long = " ".join(["mot"] * (request.model_words + 1)) + "."
    model = StandIn(long, "Le marché croît.")
    text, verified, _ = all_checks(model, request)
    assert verified and text == "Le marché croît."
    assert f"{request.model_words + 1} mots pour {request.model_words} au plus" in model.prompts[1]
    text, verified, problem = all_checks(StandIn(long, long), request)
    assert not verified and problem.endswith(f"mots pour {request.model_words} au plus")


def test_a_forbidden_phrase_is_regenerated_on_its_pages_only(warehouse):
    rules = ai.load_settings()["formulations_interdites"]
    requests = requests_of(warehouse)
    business = next(r for r in requests if r.page == ai.PAGE_BUSINESS)
    model = StandIn("Le payback n'est atteint dans aucune des deux villes.", "Les deux formats.")
    text, verified, _ = all_checks(model, business, rules)
    assert verified and text == "Les deux formats."
    assert "formulation interdite « deux villes »" in model.prompts[1]
    # "coût au m²" is forbidden everywhere; "coût moyen au m²", a KPI of the warehouse, is not.
    assert ai.forbidden_phrases("Un coût au m² de 1,02.", ai.PAGE_SLIDE, rules)
    assert not ai.forbidden_phrases(
        "Le coût moyen au m² du centre commercial.", ai.PAGE_SLIDE, rules
    )
    # No verdict on the dashboard; the slide may give one.
    for page in ai.DASHBOARD_PAGES:
        assert ai.forbidden_phrases("Le critère est GO.", page, rules)
        assert ai.forbidden_phrases("Nous recommandons Berlin.", page, rules)
        assert ai.forbidden_phrases("L’équipe retient le centre commercial.", page, rules)
    assert not ai.forbidden_phrases("NO-GO en l'état, GO conditionnel.", ai.PAGE_SLIDE, rules)
    assert not ai.forbidden_phrases("Le centre-ville de Hugo.", ai.PAGE_MARKET, rules)


def test_regenerations_stop_at_the_configured_number(warehouse):
    request = next(r for r in requests_of(warehouse) if r.valeur_filtre == "Allemagne")
    model = StandIn("Croissance de 9,9 %.", "Croissance de 9,9 %.", "Croissance de 9,9 %.", "x")
    _, verified, _ = all_checks(model, request, regenerations=2)
    assert not verified and len(model.prompts) == 3


def test_the_team_sentence_ends_the_slide_word_for_word(warehouse):
    slide = requests_of(warehouse)[-1]
    text, verified, _ = all_checks(StandIn("Contexte\nRecommandation\nNO-GO en l'état."), slide)
    assert verified and text == f"Contexte\nRecommandation\nNO-GO en l'état. {slide.ending}"
    # An empty answer gets no ending: it stays an empty, rejected text.
    text, verified, _ = all_checks(StandIn("", ""), slide)
    assert (text, verified) == ("", False)


# -- Three checks kept apart (Jean-Li, 13/11/2026) --------------------------------------
def test_a_long_text_with_right_numbers_stays_verified(warehouse):
    """verifie is about the numbers only: a text over its limit is still shown."""
    request = next(r for r in requests_of(warehouse) if r.valeur_filtre == "Allemagne")
    long = "Croissance de 4,21 %. " + " ".join(["mot"] * request.model_words)
    outcome = ai.comment(StandIn(long, long), request)
    assert outcome.verifie and not outcome.longueur_ok and outcome.formulations_ok


def test_the_best_attempt_is_kept_the_numbers_first(warehouse):
    request = next(r for r in requests_of(warehouse) if r.valeur_filtre == "Allemagne")
    long = "Croissance de 4,21 %. " + " ".join(["mot"] * request.model_words)
    # The second attempt is short but invents a number: the first one is kept.
    outcome = ai.comment(StandIn(long, "Croissance de 9,9 %."), request)
    assert outcome.text == ai.normalize_numbers(long) and outcome.verifie


def test_a_forbidden_phrase_is_reported_apart(warehouse):
    rules = ai.load_settings()["formulations_interdites"]
    request = next(r for r in requests_of(warehouse) if r.valeur_filtre == "Allemagne")
    outcome = ai.comment(StandIn("Le critère est GO.", "Le critère est GO."), request, rules)
    assert outcome.verifie and outcome.longueur_ok and not outcome.formulations_ok


def test_the_pessimistic_page_ends_on_the_team_sentence_without_the_payback_rows(warehouse):
    request = next(r for r in requests_of(warehouse) if r.valeur_filtre == "pessimiste")
    sentence = ai.load_settings()["phrases_equipe"][0]["phrase"]
    assert request.ending == sentence
    assert not any(line.startswith("- Payback") for line in request.lines)
    outcome = ai.comment(StandIn("Le coût d'occupation dépasse son seuil."), request)
    assert outcome.text == f"Le coût d'occupation dépasse son seuil. {sentence}"
    # The other scenarios keep their payback rows and get no sentence.
    central = next(r for r in requests_of(warehouse) if r.valeur_filtre == "central")
    assert central.ending is None and any(line.startswith("- Payback") for line in central.lines)


def test_the_german_break_even_is_compared_to_france_on_the_same_scope():
    rows = [
        {"kpi": "Point mort par magasin : Centre commercial", "pays": "FR", "valeur": 412861.0},
        {
            "kpi": "Point mort par magasin (même périmètre que l'Allemagne) : Centre commercial",
            "pays": "FR",
            "valeur": 540354.0,
            "unite": "€ de CA HT/an",
        },
    ]
    reference = ai.france_references(rows)["Point mort par magasin : Centre commercial"]
    assert reference["valeur"] == 540354.0
    german = {
        "kpi": "Point mort par magasin : Centre commercial",
        "pays": "DE",
        "axe": "Rentabilité",
        "valeur": 565010.0,
        "unite": "€ de CA HT/an",
        "seuil": None,
        "statut_go": "INFO",
        "statut_epistemique": "CALCUL",
        "origine_donnees": "SIMULE",
    }
    line = ai.render_kpi(german, verdict=False, france=reference)
    assert "France, même périmètre de coûts : 540\u00a0354 € de CA HT/an" in line
    assert "écart à la France : +24\u00a0656 € de CA HT/an" in line


def test_a_signed_gap_is_read_by_the_guard_rail():
    line = "écart à la France : \u221210,06 points | écart au seuil : +2,21 points"
    allowed = ai.allowed_values(line)
    assert (
        ai.unsupported_numbers("Un écart de \u221210,06 points, et de +2,21 points.", allowed) == []
    )
    assert ai.unsupported_numbers("Un écart de -10,06 points.", allowed) == []
