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
    ]


def test_a_market_request_only_sees_its_country_and_its_axes(warehouse):
    germany = next(r for r in requests_of(warehouse) if r.valeur_filtre == "Allemagne")
    text = "\n".join(germany.lines)
    assert "4,21 %" in text and "101,5 indice" in text
    assert "3,05" not in text  # France
    assert "1480" not in text  # Réseau axis
    assert "Payback" not in text  # Rentabilité axis


def test_a_business_request_only_sees_its_scenario_and_the_common_rows(warehouse):
    central = next(r for r in requests_of(warehouse) if r.valeur_filtre == "central")
    text = "\n".join(central.lines)
    assert "scénario central" in text and "Point mort" in text
    assert "pessimiste" not in text


def test_a_missing_payback_is_said_not_reached(warehouse):
    pessimistic = next(r for r in requests_of(warehouse) if r.valeur_filtre == "pessimiste")
    assert ai.MISSING_PAYBACK in "\n".join(pessimistic.lines)


def test_the_synthesis_counts_the_verdicts(warehouse):
    synthesis = requests_of(warehouse)[0]
    assert synthesis.template == "synthese.md"
    assert synthesis.lines[-2] == "- Verdicts des KPI à seuil : 1 GO, 1 NO-GO"


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
        without = ai.build_requests(con, {**config, "decision": None})[0].lines
        with_decision = ai.build_requests(con, {**config, "decision": decision})[0].lines
    finally:
        con.close()
    assert without[-1] == ai.DECISION_OPEN
    assert with_decision[-3:] == (
        "- décision retenue par l'équipe / verdict : NO-GO en l'état, GO conditionnel",
        "- décision retenue par l'équipe / conditions : environ 3 ETP ; CA/m² ≥ France + 2 % ; "
        "centre commercial",
        "- décision retenue par l'équipe / approvisionnement / hub : Dordrecht",
    )
    # The figures of the decision may then be quoted: they are part of the prompt.
    synthesis = ai.build_requests(
        con := duckdb.connect(str(warehouse), read_only=True), {**config, "decision": decision}
    )[0]
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
    assert "100 000 habitants" in text
    weights = ai.load_config()["city_scoring"]["poids"]
    assert all(f"{criterion} {weight}" in text for criterion, weight in weights.items())


# -- Generation ------------------------------------------------------------------------
def test_an_unsupported_number_triggers_one_regeneration(warehouse):
    request = next(r for r in requests_of(warehouse) if r.valeur_filtre == "Allemagne")
    model = StandIn("Croissance de 9,9 %.", "Croissance de 4,2 % (données simulées).")
    text, verified, _ = ai.comment(model, request)
    assert verified and text == "Croissance de 4,2 % (données simulées)."
    assert len(model.prompts) == 2 and "9,9" in model.prompts[1]


def test_a_number_quoted_in_the_correction_does_not_become_allowed(warehouse):
    request = next(r for r in requests_of(warehouse) if r.valeur_filtre == "Allemagne")
    model = StandIn("Croissance de 9,9 %.", "Croissance de 9,9 %.")
    text, verified, problem = ai.comment(model, request)
    assert not verified and text == "Croissance de 9,9 %."
    assert problem == "chiffres hors données : 9,9"


def test_an_empty_text_is_never_verified(warehouse):
    """No number at all passes a check of the numbers: emptiness is checked first."""
    request = next(r for r in requests_of(warehouse) if r.valeur_filtre == "Allemagne")
    text, verified, problem = ai.comment(StandIn("", ""), request)
    assert (text, verified, problem) == ("", False, "texte vide")
    # A second, complete answer is accepted.
    text, verified, _ = ai.comment(StandIn("", "Marché porteur."), request)
    assert verified and text == "Marché porteur."


def test_a_truncated_text_is_never_verified(warehouse):
    """A text cut at max_tokens may hold only right numbers: it is rejected all the same."""
    request = next(r for r in requests_of(warehouse) if r.valeur_filtre == "Allemagne")
    cut = ai.TruncatedAnswer("Croissance de 4,21 %, devant")
    text, verified, problem = ai.comment(StandIn(cut, cut), request)
    assert (text, verified, problem) == ("Croissance de 4,21 %, devant", False, "texte tronqué")
    model = StandIn(cut, "Croissance de 4,21 % (données simulées).")
    text, verified, _ = ai.comment(model, request)
    assert verified and model.prompts[0] == model.prompts[1]  # same prompt, no correction


def test_the_throttle_waits_between_calls_only():
    waits = []
    model = ai.Throttled(StandIn("a", "b", "c"), 1.2, waits.append)
    for _ in range(3):
        model.generate("system", "user")
    assert waits == [1.2, 1.2]


def test_run_writes_the_csv_and_the_table(warehouse, tmp_path):
    out = tmp_path / "ai_commentary.csv"
    synthesis = "Contexte\nMarché en croissance de 4,21 %.\nRecommandation\nNO-GO."
    model = StandIn(synthesis)
    rows = ai.run(
        warehouse,
        out,
        model,
        SETTINGS,
        sleep=lambda _: None,
        now=lambda: datetime(2026, 11, 12, 15, 0, 0),
    )
    assert len(rows) == 7

    with out.open(encoding="utf-8", newline="") as file:
        written = list(csv.DictReader(file))
    assert list(written[0]) == ai.COLUMNS
    assert written[0]["texte"] == synthesis  # the line breaks survive the CSV file
    assert {row["verifie"] for row in written} == {"true"}
    assert written[0]["date_generation"] == "2026-11-12T15:00:00"

    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        types = dict(con.execute(f"DESCRIBE {ai.TABLE}").fetchall()[i][:2] for i in range(6))
        assert types["verifie"] == "BOOLEAN" and types["date_generation"] == "TIMESTAMP"
        assert con.execute(f"SELECT count(*) FROM {ai.TABLE}").fetchone()[0] == 7
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


def test_the_synthesis_is_asked_to_fit_in_a_text_box(warehouse):
    """A synthesis without a limit was cut at max_tokens, after 816 words (12/11/2026)."""
    synthesis = requests_of(warehouse)[0]
    limit = ai.load_settings()["synthese_mots_max"]
    assert synthesis.max_words == limit
    assert f"en {limit} mots au plus" in ai.user_prompt(synthesis)
    # The page comments have no word limit of their own: two or three sentences.
    market = next(r for r in requests_of(warehouse) if r.page == ai.PAGE_MARKET)
    assert market.max_words is None and "deux ou trois phrases" in ai.user_prompt(market)
