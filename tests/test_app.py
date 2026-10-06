from streamlit.testing.v1 import AppTest

from bioze.paths import project_path


def test_home_and_missing_cbs_outputs_render_without_exceptions():
    home = AppTest.from_file(str(project_path("Home.py")), default_timeout=30).run()
    assert not home.exception
    assert any("betere afweging" in title.value for title in home.title)
    cbs = AppTest.from_file(str(project_path("pages", "3_CBS_Woningverkenner.py")), default_timeout=30).run()
    assert not cbs.exception
    assert any("niet meegeleverd" in message.value for message in cbs.info)


def test_complete_analysis_to_policy_and_stale_result_invalidation():
    phase1 = AppTest.from_file(str(project_path("Home.py")), default_timeout=30).run()
    phase1.switch_page("pages/1_Fase_1_Geschiktheidsanalyse.py").run()
    assert not phase1.exception
    phase1.button[0].click().run()
    assert not phase1.exception
    sites = phase1.session_state.candidates
    assert len(sites) > 0
    phase2 = AppTest.from_file(str(project_path("Home.py")), default_timeout=30).run()
    phase2.switch_page("pages/2_Fase_2_Beleidsverkenner.py")
    phase2.session_state.candidates = sites
    phase2.run()
    assert not phase2.exception
    assert phase2.button[0].disabled
    phase2.checkbox[0].check().run()
    phase2.button[0].click().run()
    assert not phase2.exception
    assert phase2.session_state.policy_result["processed"] == 17500
    phase2.slider[0].set_value(75).run()
    assert not phase2.exception
    assert "policy_result" not in phase2.session_state
    phase1.slider[0].set_value(3).run()
    assert not phase1.exception
    assert "candidates" not in phase1.session_state


def test_empty_criteria_clear_previous_candidates():
    app = AppTest.from_file(str(project_path("Home.py")), default_timeout=30).run()
    app.switch_page("pages/1_Fase_1_Geschiktheidsanalyse.py").run()
    app.button[0].click().run()
    assert "candidates" in app.session_state
    app.multiselect[0].set_value([]).run()
    assert not app.exception
    assert "candidates" not in app.session_state
    assert "analysis_scores" not in app.session_state
