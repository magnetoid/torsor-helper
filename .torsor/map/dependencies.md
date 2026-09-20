---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-21T01:02:55'
updated: '2026-09-21T01:02:55'
rules: []
---

# Module dependencies

## Module dependencies

```mermaid
graph TD
    n_tests_bench_bench["tests.bench.bench"]
    n_tests_bench_generate["tests.bench.generate"]
    n_tests_test_ambiguous_links["tests.test_ambiguous_links"]
    n_tests_test_auto_handoff["tests.test_auto_handoff"]
    n_tests_test_baseline["tests.test_baseline"]
    n_tests_test_budget["tests.test_budget"]
    n_tests_test_cartographer_edges["tests.test_cartographer_edges"]
    n_tests_test_cartographer_extract["tests.test_cartographer_extract"]
    n_tests_test_cartographer_render["tests.test_cartographer_render"]
    n_tests_test_cartographer_scan["tests.test_cartographer_scan"]
    n_tests_test_check_drift["tests.test_check_drift"]
    n_tests_test_clean_op["tests.test_clean_op"]
    n_tests_test_cleaner["tests.test_cleaner"]
    n_tests_test_cli["tests.test_cli"]
    n_tests_test_cli_clean["tests.test_cli_clean"]
    n_tests_test_cli_coach["tests.test_cli_coach"]
    n_tests_test_cli_consolidate["tests.test_cli_consolidate"]
    n_tests_test_cli_guard["tests.test_cli_guard"]
    n_tests_test_cli_hooks["tests.test_cli_hooks"]
    n_tests_test_cli_index["tests.test_cli_index"]
    n_tests_test_cli_map["tests.test_cli_map"]
    n_tests_test_cli_stale["tests.test_cli_stale"]
    n_tests_test_cli_verify["tests.test_cli_verify"]
    n_tests_test_client_instructions["tests.test_client_instructions"]
    n_tests_test_clients["tests.test_clients"]
    n_tests_test_coach_coupling["tests.test_coach_coupling"]
    n_tests_test_coach_health["tests.test_coach_health"]
    n_tests_test_coach_hooks["tests.test_coach_hooks"]
    n_tests_test_coach_hotspots["tests.test_coach_hotspots"]
    n_tests_test_coach_hubs["tests.test_coach_hubs"]
    n_tests_test_coach_mining["tests.test_coach_mining"]
    n_tests_test_coach_models["tests.test_coach_models"]
    n_tests_test_coach_recommender["tests.test_coach_recommender"]
    n_tests_test_coach_report["tests.test_coach_report"]
    n_tests_test_coach_staleness["tests.test_coach_staleness"]
    n_tests_test_coach_state["tests.test_coach_state"]
    n_tests_test_coach_trend["tests.test_coach_trend"]
    n_tests_test_commands["tests.test_commands"]
    n_tests_test_complexity_multilang["tests.test_complexity_multilang"]
    n_tests_test_config["tests.test_config"]
    n_tests_test_config_automation["tests.test_config_automation"]
    n_tests_test_config_index["tests.test_config_index"]
    n_tests_test_connect["tests.test_connect"]
    n_tests_test_consolidate_op["tests.test_consolidate_op"]
    n_tests_test_db_symbols["tests.test_db_symbols"]
    n_tests_test_edit_gate["tests.test_edit_gate"]
    n_tests_test_embeddings["tests.test_embeddings"]
    n_tests_test_export["tests.test_export"]
    n_tests_test_export_map_clash["tests.test_export_map_clash"]
    n_tests_test_finder["tests.test_finder"]
    n_tests_test_flags_mean_what_they_say["tests.test_flags_mean_what_they_say"]
    n_tests_test_frontmatter_robustness["tests.test_frontmatter_robustness"]
    n_tests_test_get_intent["tests.test_get_intent"]
    n_tests_test_guard_checks["tests.test_guard_checks"]
    n_tests_test_guard_multilang["tests.test_guard_multilang"]
    n_tests_test_guard_rules["tests.test_guard_rules"]
    n_tests_test_hooks_safety["tests.test_hooks_safety"]
    n_tests_test_http_transport["tests.test_http_transport"]
    n_tests_test_impact["tests.test_impact"]
    n_tests_test_index_not_authoritative["tests.test_index_not_authoritative"]
    n_tests_test_index_open_cost["tests.test_index_open_cost"]
    n_tests_test_indexer["tests.test_indexer"]
    n_tests_test_indexer_breadcrumb["tests.test_indexer_breadcrumb"]
    n_tests_test_init_write["tests.test_init_write"]
    n_tests_test_lang_go["tests.test_lang_go"]
    n_tests_test_languages_registry["tests.test_languages_registry"]
    n_tests_test_map_fingerprint["tests.test_map_fingerprint"]
    n_tests_test_map_multilang["tests.test_map_multilang"]
    n_tests_test_map_repo["tests.test_map_repo"]
    n_tests_test_map_repo_partial["tests.test_map_repo_partial"]
    n_tests_test_models["tests.test_models"]
    n_tests_test_models_tiering["tests.test_models_tiering"]
    n_tests_test_multilang_discoverability["tests.test_multilang_discoverability"]
    n_tests_test_multilang_seams["tests.test_multilang_seams"]
    n_tests_test_on_commit["tests.test_on_commit"]
    n_tests_test_operations["tests.test_operations"]
    n_tests_test_path_containment["tests.test_path_containment"]
    n_tests_test_paths["tests.test_paths"]
    n_tests_test_practices["tests.test_practices"]
    n_tests_test_recall["tests.test_recall"]
    n_tests_test_recall_via_index["tests.test_recall_via_index"]
    n_tests_test_recipes["tests.test_recipes"]
    n_tests_test_recommend_op["tests.test_recommend_op"]
    n_tests_test_record_decision["tests.test_record_decision"]
    n_tests_test_safety_gates["tests.test_safety_gates"]
    n_tests_test_scope_matching["tests.test_scope_matching"]
    n_tests_test_scoped_rules["tests.test_scoped_rules"]
    n_tests_test_search["tests.test_search"]
    n_tests_test_search_importance["tests.test_search_importance"]
    n_tests_test_search_mmr["tests.test_search_mmr"]
    n_tests_test_server["tests.test_server"]
    n_tests_test_server_guard["tests.test_server_guard"]
    n_tests_test_server_hooks["tests.test_server_hooks"]
    n_tests_test_server_map_intent["tests.test_server_map_intent"]
    n_tests_test_server_verify["tests.test_server_verify"]
    n_tests_test_session_start["tests.test_session_start"]
    n_tests_test_snippets["tests.test_snippets"]
    n_tests_test_stale_op["tests.test_stale_op"]
    n_tests_test_state_dir["tests.test_state_dir"]
    n_tests_test_store_io["tests.test_store_io"]
    n_tests_test_store_parsing["tests.test_store_parsing"]
    n_tests_test_templates["tests.test_templates"]
    n_tests_test_tier_weights["tests.test_tier_weights"]
    n_tests_test_token_budgets["tests.test_token_budgets"]
    n_tests_test_updater_primer["tests.test_updater_primer"]
    n_tests_test_verify_op["tests.test_verify_op"]
    n_tests_test_wikilink_forms["tests.test_wikilink_forms"]
    n_torsor_helper_baseline["torsor_helper.baseline"]
    n_torsor_helper_budget["torsor_helper.budget"]
    n_torsor_helper_cartographer["torsor_helper.cartographer"]
    n_torsor_helper_cli["torsor_helper.cli"]
    n_torsor_helper_clients["torsor_helper.clients"]
    n_torsor_helper_coach_coupling["torsor_helper.coach.coupling"]
    n_torsor_helper_coach_health["torsor_helper.coach.health"]
    n_torsor_helper_coach_hotspots["torsor_helper.coach.hotspots"]
    n_torsor_helper_coach_hubs["torsor_helper.coach.hubs"]
    n_torsor_helper_coach_mining["torsor_helper.coach.mining"]
    n_torsor_helper_coach_recommender["torsor_helper.coach.recommender"]
    n_torsor_helper_coach_report["torsor_helper.coach.report"]
    n_torsor_helper_coach_staleness["torsor_helper.coach.staleness"]
    n_torsor_helper_coach_state["torsor_helper.coach.state"]
    n_torsor_helper_coach_trend["torsor_helper.coach.trend"]
    n_torsor_helper_config["torsor_helper.config"]
    n_torsor_helper_db["torsor_helper.db"]
    n_torsor_helper_deps["torsor_helper.deps"]
    n_torsor_helper_embeddings["torsor_helper.embeddings"]
    n_torsor_helper_export["torsor_helper.export"]
    n_torsor_helper_finder["torsor_helper.finder"]
    n_torsor_helper_guard["torsor_helper.guard"]
    n_torsor_helper_indexer["torsor_helper.indexer"]
    n_torsor_helper_languages___init__["torsor_helper.languages.__init__"]
    n_torsor_helper_languages_go["torsor_helper.languages.go"]
    n_torsor_helper_languages_javascript["torsor_helper.languages.javascript"]
    n_torsor_helper_languages_modules["torsor_helper.languages.modules"]
    n_torsor_helper_languages_python["torsor_helper.languages.python"]
    n_torsor_helper_models["torsor_helper.models"]
    n_torsor_helper_operations__shared["torsor_helper.operations._shared"]
    n_torsor_helper_operations__state["torsor_helper.operations._state"]
    n_torsor_helper_operations_capture["torsor_helper.operations.capture"]
    n_torsor_helper_operations_commands["torsor_helper.operations.commands"]
    n_torsor_helper_operations_decisions["torsor_helper.operations.decisions"]
    n_torsor_helper_operations_gate["torsor_helper.operations.gate"]
    n_torsor_helper_operations_graph["torsor_helper.operations.graph"]
    n_torsor_helper_operations_hooks_ops["torsor_helper.operations.hooks_ops"]
    n_torsor_helper_operations_maintenance["torsor_helper.operations.maintenance"]
    n_torsor_helper_operations_memory["torsor_helper.operations.memory"]
    n_torsor_helper_operations_prompt_blocks["torsor_helper.operations.prompt_blocks"]
    n_torsor_helper_paths["torsor_helper.paths"]
    n_torsor_helper_practices["torsor_helper.practices"]
    n_torsor_helper_recall["torsor_helper.recall"]
    n_torsor_helper_search["torsor_helper.search"]
    n_torsor_helper_server["torsor_helper.server"]
    n_torsor_helper_snippets["torsor_helper.snippets"]
    n_torsor_helper_store["torsor_helper.store"]
    n_torsor_helper_templates["torsor_helper.templates"]
    n_tests_bench_bench --> n_torsor_helper_config
    n_tests_bench_generate --> n_torsor_helper_paths
    n_tests_bench_generate --> n_torsor_helper_store
    n_tests_test_ambiguous_links --> n_torsor_helper_paths
    n_tests_test_ambiguous_links --> n_torsor_helper_store
    n_tests_test_auto_handoff --> n_torsor_helper_config
    n_tests_test_auto_handoff --> n_torsor_helper_paths
    n_tests_test_auto_handoff --> n_torsor_helper_store
    n_tests_test_baseline --> n_torsor_helper_config
    n_tests_test_baseline --> n_torsor_helper_models
    n_tests_test_baseline --> n_torsor_helper_paths
    n_tests_test_baseline --> n_torsor_helper_store
    n_tests_test_budget --> n_torsor_helper_budget
    n_tests_test_cartographer_edges --> n_torsor_helper_cartographer
    n_tests_test_cartographer_extract --> n_torsor_helper_cartographer
    n_tests_test_cartographer_render --> n_torsor_helper_cartographer
    n_tests_test_cartographer_render --> n_torsor_helper_models
    n_tests_test_cartographer_scan --> n_torsor_helper_cartographer
    n_tests_test_check_drift --> n_torsor_helper_config
    n_tests_test_check_drift --> n_torsor_helper_paths
    n_tests_test_check_drift --> n_torsor_helper_store
    n_tests_test_clean_op --> n_torsor_helper_config
    n_tests_test_clean_op --> n_torsor_helper_paths
    n_tests_test_clean_op --> n_torsor_helper_store
    n_tests_test_cleaner --> n_torsor_helper_config
    n_tests_test_cleaner --> n_torsor_helper_paths
    n_tests_test_cleaner --> n_torsor_helper_store
    n_tests_test_cli --> n_torsor_helper_cli
    n_tests_test_cli --> n_torsor_helper_paths
    n_tests_test_cli_clean --> n_torsor_helper_cli
    n_tests_test_cli_clean --> n_torsor_helper_server
    n_tests_test_cli_coach --> n_torsor_helper_cli
    n_tests_test_cli_consolidate --> n_torsor_helper_cli
    n_tests_test_cli_consolidate --> n_torsor_helper_server
    n_tests_test_cli_guard --> n_torsor_helper_cli
    n_tests_test_cli_guard --> n_torsor_helper_paths
    n_tests_test_cli_guard --> n_torsor_helper_store
    n_tests_test_cli_hooks --> n_torsor_helper_cli
    n_tests_test_cli_index --> n_torsor_helper_cli
    n_tests_test_cli_index --> n_torsor_helper_paths
    n_tests_test_cli_map --> n_torsor_helper_cli
    n_tests_test_cli_map --> n_torsor_helper_paths
    n_tests_test_cli_stale --> n_torsor_helper_cli
    n_tests_test_cli_stale --> n_torsor_helper_models
    n_tests_test_cli_stale --> n_torsor_helper_paths
    n_tests_test_cli_stale --> n_torsor_helper_store
    n_tests_test_cli_verify --> n_torsor_helper_cli
    n_tests_test_cli_verify --> n_torsor_helper_paths
    n_tests_test_cli_verify --> n_torsor_helper_store
    n_tests_test_client_instructions --> n_torsor_helper_cli
    n_tests_test_clients --> n_torsor_helper_clients
    n_tests_test_coach_coupling --> n_torsor_helper_embeddings
    n_tests_test_coach_coupling --> n_torsor_helper_indexer
    n_tests_test_coach_coupling --> n_torsor_helper_paths
    n_tests_test_coach_coupling --> n_torsor_helper_store
    n_tests_test_coach_health --> n_torsor_helper_paths
    n_tests_test_coach_health --> n_torsor_helper_store
    n_tests_test_coach_hooks --> n_torsor_helper_paths
    n_tests_test_coach_hooks --> n_torsor_helper_server
    n_tests_test_coach_hooks --> n_torsor_helper_store
    n_tests_test_coach_hotspots --> n_torsor_helper_config
    n_tests_test_coach_hotspots --> n_torsor_helper_embeddings
    n_tests_test_coach_hotspots --> n_torsor_helper_indexer
    n_tests_test_coach_hotspots --> n_torsor_helper_paths
    n_tests_test_coach_hotspots --> n_torsor_helper_store
    n_tests_test_coach_hubs --> n_torsor_helper_config
    n_tests_test_coach_hubs --> n_torsor_helper_paths
    n_tests_test_coach_hubs --> n_torsor_helper_store
    n_tests_test_coach_mining --> n_torsor_helper_paths
    n_tests_test_coach_mining --> n_torsor_helper_store
    n_tests_test_coach_models --> n_torsor_helper_models
    n_tests_test_coach_recommender --> n_torsor_helper_coach_recommender
    n_tests_test_coach_recommender --> n_torsor_helper_config
    n_tests_test_coach_recommender --> n_torsor_helper_embeddings
    n_tests_test_coach_recommender --> n_torsor_helper_indexer
    n_tests_test_coach_recommender --> n_torsor_helper_models
    n_tests_test_coach_recommender --> n_torsor_helper_paths
    n_tests_test_coach_recommender --> n_torsor_helper_store
    n_tests_test_coach_report --> n_torsor_helper_coach_state
    n_tests_test_coach_report --> n_torsor_helper_config
    n_tests_test_coach_report --> n_torsor_helper_paths
    n_tests_test_coach_report --> n_torsor_helper_store
    n_tests_test_coach_staleness --> n_torsor_helper_models
    n_tests_test_coach_staleness --> n_torsor_helper_paths
    n_tests_test_coach_staleness --> n_torsor_helper_store
    n_tests_test_coach_state --> n_torsor_helper_coach_state
    n_tests_test_coach_trend --> n_torsor_helper_config
    n_tests_test_coach_trend --> n_torsor_helper_paths
    n_tests_test_coach_trend --> n_torsor_helper_store
    n_tests_test_commands --> n_torsor_helper_cli
    n_tests_test_commands --> n_torsor_helper_config
    n_tests_test_commands --> n_torsor_helper_paths
    n_tests_test_commands --> n_torsor_helper_store
    n_tests_test_complexity_multilang --> n_torsor_helper_coach_hotspots
    n_tests_test_config --> n_torsor_helper_config
    n_tests_test_config --> n_torsor_helper_paths
    n_tests_test_config_automation --> n_torsor_helper_config
    n_tests_test_config_automation --> n_torsor_helper_paths
    n_tests_test_config_index --> n_torsor_helper_config
    n_tests_test_connect --> n_torsor_helper_config
    n_tests_test_connect --> n_torsor_helper_paths
    n_tests_test_connect --> n_torsor_helper_store
    n_tests_test_consolidate_op --> n_torsor_helper_config
    n_tests_test_consolidate_op --> n_torsor_helper_paths
    n_tests_test_consolidate_op --> n_torsor_helper_store
    n_tests_test_db_symbols --> n_torsor_helper_models
    n_tests_test_edit_gate --> n_torsor_helper_cli
    n_tests_test_edit_gate --> n_torsor_helper_config
    n_tests_test_edit_gate --> n_torsor_helper_paths
    n_tests_test_edit_gate --> n_torsor_helper_store
    n_tests_test_embeddings --> n_torsor_helper_config
    n_tests_test_embeddings --> n_torsor_helper_embeddings
    n_tests_test_export --> n_torsor_helper_config
    n_tests_test_export --> n_torsor_helper_paths
    n_tests_test_export --> n_torsor_helper_store
    n_tests_test_export_map_clash --> n_torsor_helper_config
    n_tests_test_export_map_clash --> n_torsor_helper_paths
    n_tests_test_export_map_clash --> n_torsor_helper_store
    n_tests_test_finder --> n_torsor_helper_config
    n_tests_test_finder --> n_torsor_helper_paths
    n_tests_test_finder --> n_torsor_helper_store
    n_tests_test_flags_mean_what_they_say --> n_torsor_helper_cli
    n_tests_test_flags_mean_what_they_say --> n_torsor_helper_config
    n_tests_test_flags_mean_what_they_say --> n_torsor_helper_paths
    n_tests_test_flags_mean_what_they_say --> n_torsor_helper_store
    n_tests_test_frontmatter_robustness --> n_torsor_helper_paths
    n_tests_test_frontmatter_robustness --> n_torsor_helper_store
    n_tests_test_get_intent --> n_torsor_helper_config
    n_tests_test_get_intent --> n_torsor_helper_paths
    n_tests_test_get_intent --> n_torsor_helper_store
    n_tests_test_guard_checks --> n_torsor_helper_guard
    n_tests_test_guard_checks --> n_torsor_helper_models
    n_tests_test_guard_checks --> n_torsor_helper_paths
    n_tests_test_guard_checks --> n_torsor_helper_store
    n_tests_test_guard_multilang --> n_torsor_helper_guard
    n_tests_test_guard_multilang --> n_torsor_helper_models
    n_tests_test_guard_rules --> n_torsor_helper_guard
    n_tests_test_guard_rules --> n_torsor_helper_models
    n_tests_test_guard_rules --> n_torsor_helper_paths
    n_tests_test_guard_rules --> n_torsor_helper_store
    n_tests_test_hooks_safety --> n_torsor_helper_config
    n_tests_test_hooks_safety --> n_torsor_helper_paths
    n_tests_test_hooks_safety --> n_torsor_helper_store
    n_tests_test_http_transport --> n_torsor_helper_server
    n_tests_test_impact --> n_torsor_helper_config
    n_tests_test_impact --> n_torsor_helper_paths
    n_tests_test_impact --> n_torsor_helper_store
    n_tests_test_index_not_authoritative --> n_torsor_helper_config
    n_tests_test_index_not_authoritative --> n_torsor_helper_paths
    n_tests_test_index_not_authoritative --> n_torsor_helper_store
    n_tests_test_index_open_cost --> n_torsor_helper_config
    n_tests_test_index_open_cost --> n_torsor_helper_paths
    n_tests_test_index_open_cost --> n_torsor_helper_store
    n_tests_test_indexer --> n_torsor_helper_embeddings
    n_tests_test_indexer --> n_torsor_helper_indexer
    n_tests_test_indexer --> n_torsor_helper_paths
    n_tests_test_indexer --> n_torsor_helper_store
    n_tests_test_indexer_breadcrumb --> n_torsor_helper_embeddings
    n_tests_test_indexer_breadcrumb --> n_torsor_helper_indexer
    n_tests_test_indexer_breadcrumb --> n_torsor_helper_paths
    n_tests_test_indexer_breadcrumb --> n_torsor_helper_store
    n_tests_test_init_write --> n_torsor_helper_cli
    n_tests_test_init_write --> n_torsor_helper_clients
    n_tests_test_lang_go --> n_torsor_helper_cartographer
    n_tests_test_languages_registry --> n_torsor_helper_languages_modules
    n_tests_test_map_fingerprint --> n_torsor_helper_config
    n_tests_test_map_fingerprint --> n_torsor_helper_paths
    n_tests_test_map_fingerprint --> n_torsor_helper_store
    n_tests_test_map_multilang --> n_torsor_helper_config
    n_tests_test_map_multilang --> n_torsor_helper_paths
    n_tests_test_map_multilang --> n_torsor_helper_store
    n_tests_test_map_repo --> n_torsor_helper_config
    n_tests_test_map_repo --> n_torsor_helper_paths
    n_tests_test_map_repo --> n_torsor_helper_store
    n_tests_test_map_repo_partial --> n_torsor_helper_config
    n_tests_test_map_repo_partial --> n_torsor_helper_paths
    n_tests_test_map_repo_partial --> n_torsor_helper_store
    n_tests_test_models --> n_torsor_helper_models
    n_tests_test_models_tiering --> n_torsor_helper_cli
    n_tests_test_models_tiering --> n_torsor_helper_config
    n_tests_test_models_tiering --> n_torsor_helper_paths
    n_tests_test_models_tiering --> n_torsor_helper_store
    n_tests_test_multilang_discoverability --> n_torsor_helper_cli
    n_tests_test_multilang_discoverability --> n_torsor_helper_config
    n_tests_test_multilang_discoverability --> n_torsor_helper_paths
    n_tests_test_multilang_discoverability --> n_torsor_helper_store
    n_tests_test_multilang_seams --> n_torsor_helper_config
    n_tests_test_multilang_seams --> n_torsor_helper_languages_modules
    n_tests_test_multilang_seams --> n_torsor_helper_paths
    n_tests_test_multilang_seams --> n_torsor_helper_store
    n_tests_test_on_commit --> n_torsor_helper_config
    n_tests_test_on_commit --> n_torsor_helper_paths
    n_tests_test_on_commit --> n_torsor_helper_store
    n_tests_test_operations --> n_torsor_helper_config
    n_tests_test_operations --> n_torsor_helper_paths
    n_tests_test_operations --> n_torsor_helper_store
    n_tests_test_path_containment --> n_torsor_helper_config
    n_tests_test_path_containment --> n_torsor_helper_paths
    n_tests_test_path_containment --> n_torsor_helper_store
    n_tests_test_paths --> n_torsor_helper_paths
    n_tests_test_practices --> n_torsor_helper_config
    n_tests_test_practices --> n_torsor_helper_guard
    n_tests_test_practices --> n_torsor_helper_paths
    n_tests_test_practices --> n_torsor_helper_store
    n_tests_test_recall --> n_torsor_helper_models
    n_tests_test_recall --> n_torsor_helper_recall
    n_tests_test_recall_via_index --> n_torsor_helper_config
    n_tests_test_recall_via_index --> n_torsor_helper_paths
    n_tests_test_recall_via_index --> n_torsor_helper_store
    n_tests_test_recipes --> n_torsor_helper_cli
    n_tests_test_recipes --> n_torsor_helper_config
    n_tests_test_recipes --> n_torsor_helper_paths
    n_tests_test_recipes --> n_torsor_helper_store
    n_tests_test_recommend_op --> n_torsor_helper_config
    n_tests_test_recommend_op --> n_torsor_helper_paths
    n_tests_test_recommend_op --> n_torsor_helper_store
    n_tests_test_record_decision --> n_torsor_helper_config
    n_tests_test_record_decision --> n_torsor_helper_guard
    n_tests_test_record_decision --> n_torsor_helper_paths
    n_tests_test_record_decision --> n_torsor_helper_store
    n_tests_test_safety_gates --> n_torsor_helper_cli
    n_tests_test_safety_gates --> n_torsor_helper_config
    n_tests_test_safety_gates --> n_torsor_helper_paths
    n_tests_test_safety_gates --> n_torsor_helper_store
    n_tests_test_scope_matching --> n_torsor_helper_guard
    n_tests_test_scoped_rules --> n_torsor_helper_cli
    n_tests_test_scoped_rules --> n_torsor_helper_config
    n_tests_test_scoped_rules --> n_torsor_helper_paths
    n_tests_test_scoped_rules --> n_torsor_helper_store
    n_tests_test_search --> n_torsor_helper_config
    n_tests_test_search --> n_torsor_helper_embeddings
    n_tests_test_search --> n_torsor_helper_indexer
    n_tests_test_search --> n_torsor_helper_paths
    n_tests_test_search --> n_torsor_helper_search
    n_tests_test_search --> n_torsor_helper_store
    n_tests_test_search_importance --> n_torsor_helper_config
    n_tests_test_search_importance --> n_torsor_helper_embeddings
    n_tests_test_search_importance --> n_torsor_helper_indexer
    n_tests_test_search_importance --> n_torsor_helper_models
    n_tests_test_search_importance --> n_torsor_helper_paths
    n_tests_test_search_importance --> n_torsor_helper_search
    n_tests_test_search_importance --> n_torsor_helper_store
    n_tests_test_search_mmr --> n_torsor_helper_config
    n_tests_test_search_mmr --> n_torsor_helper_embeddings
    n_tests_test_search_mmr --> n_torsor_helper_indexer
    n_tests_test_search_mmr --> n_torsor_helper_models
    n_tests_test_search_mmr --> n_torsor_helper_paths
    n_tests_test_search_mmr --> n_torsor_helper_search
    n_tests_test_search_mmr --> n_torsor_helper_store
    n_tests_test_server --> n_torsor_helper_server
    n_tests_test_server_guard --> n_torsor_helper_server
    n_tests_test_server_hooks --> n_torsor_helper_server
    n_tests_test_server_map_intent --> n_torsor_helper_server
    n_tests_test_server_verify --> n_torsor_helper_server
    n_tests_test_session_start --> n_torsor_helper_cli
    n_tests_test_session_start --> n_torsor_helper_config
    n_tests_test_session_start --> n_torsor_helper_paths
    n_tests_test_session_start --> n_torsor_helper_store
    n_tests_test_snippets --> n_torsor_helper_snippets
    n_tests_test_stale_op --> n_torsor_helper_config
    n_tests_test_stale_op --> n_torsor_helper_models
    n_tests_test_stale_op --> n_torsor_helper_paths
    n_tests_test_stale_op --> n_torsor_helper_store
    n_tests_test_state_dir --> n_torsor_helper_cli
    n_tests_test_state_dir --> n_torsor_helper_coach_state
    n_tests_test_state_dir --> n_torsor_helper_paths
    n_tests_test_state_dir --> n_torsor_helper_store
    n_tests_test_store_io --> n_torsor_helper_models
    n_tests_test_store_io --> n_torsor_helper_paths
    n_tests_test_store_io --> n_torsor_helper_store
    n_tests_test_store_parsing --> n_torsor_helper_models
    n_tests_test_store_parsing --> n_torsor_helper_paths
    n_tests_test_store_parsing --> n_torsor_helper_store
    n_tests_test_templates --> n_torsor_helper_paths
    n_tests_test_templates --> n_torsor_helper_templates
    n_tests_test_tier_weights --> n_torsor_helper_models
    n_tests_test_token_budgets --> n_torsor_helper_budget
    n_tests_test_token_budgets --> n_torsor_helper_config
    n_tests_test_token_budgets --> n_torsor_helper_paths
    n_tests_test_token_budgets --> n_torsor_helper_store
    n_tests_test_updater_primer --> n_torsor_helper_config
    n_tests_test_updater_primer --> n_torsor_helper_paths
    n_tests_test_updater_primer --> n_torsor_helper_store
    n_tests_test_verify_op --> n_torsor_helper_config
    n_tests_test_verify_op --> n_torsor_helper_models
    n_tests_test_verify_op --> n_torsor_helper_paths
    n_tests_test_verify_op --> n_torsor_helper_store
    n_tests_test_wikilink_forms --> n_torsor_helper_paths
    n_tests_test_wikilink_forms --> n_torsor_helper_store
    n_torsor_helper_baseline --> n_torsor_helper_models
    n_torsor_helper_cartographer --> n_torsor_helper_budget
    n_torsor_helper_cartographer --> n_torsor_helper_languages_modules
    n_torsor_helper_cartographer --> n_torsor_helper_models
    n_torsor_helper_cartographer --> n_torsor_helper_paths
    n_torsor_helper_cli --> n_torsor_helper_clients
    n_torsor_helper_cli --> n_torsor_helper_config
    n_torsor_helper_cli --> n_torsor_helper_embeddings
    n_torsor_helper_cli --> n_torsor_helper_indexer
    n_torsor_helper_cli --> n_torsor_helper_paths
    n_torsor_helper_cli --> n_torsor_helper_store
    n_torsor_helper_coach_coupling --> n_torsor_helper_cartographer
    n_torsor_helper_coach_coupling --> n_torsor_helper_coach_hotspots
    n_torsor_helper_coach_coupling --> n_torsor_helper_models
    n_torsor_helper_coach_health --> n_torsor_helper_guard
    n_torsor_helper_coach_health --> n_torsor_helper_models
    n_torsor_helper_coach_health --> n_torsor_helper_store
    n_torsor_helper_coach_hotspots --> n_torsor_helper_cartographer
    n_torsor_helper_coach_hotspots --> n_torsor_helper_models
    n_torsor_helper_coach_hubs --> n_torsor_helper_cartographer
    n_torsor_helper_coach_hubs --> n_torsor_helper_models
    n_torsor_helper_coach_mining --> n_torsor_helper_models
    n_torsor_helper_coach_mining --> n_torsor_helper_store
    n_torsor_helper_coach_recommender --> n_torsor_helper_models
    n_torsor_helper_coach_recommender --> n_torsor_helper_search
    n_torsor_helper_coach_recommender --> n_torsor_helper_store
    n_torsor_helper_coach_report --> n_torsor_helper_coach_state
    n_torsor_helper_coach_report --> n_torsor_helper_models
    n_torsor_helper_coach_report --> n_torsor_helper_store
    n_torsor_helper_coach_staleness --> n_torsor_helper_models
    n_torsor_helper_coach_staleness --> n_torsor_helper_store
    n_torsor_helper_coach_trend --> n_torsor_helper_cartographer
    n_torsor_helper_coach_trend --> n_torsor_helper_coach_hotspots
    n_torsor_helper_coach_trend --> n_torsor_helper_models
    n_torsor_helper_config --> n_torsor_helper_paths
    n_torsor_helper_db --> n_torsor_helper_models
    n_torsor_helper_deps --> n_torsor_helper_cartographer
    n_torsor_helper_export --> n_torsor_helper_cartographer
    n_torsor_helper_export --> n_torsor_helper_models
    n_torsor_helper_export --> n_torsor_helper_store
    n_torsor_helper_finder --> n_torsor_helper_cartographer
    n_torsor_helper_guard --> n_torsor_helper_cartographer
    n_torsor_helper_guard --> n_torsor_helper_models
    n_torsor_helper_guard --> n_torsor_helper_paths
    n_torsor_helper_guard --> n_torsor_helper_store
    n_torsor_helper_indexer --> n_torsor_helper_store
    n_torsor_helper_languages___init__ --> n_torsor_helper_models
    n_torsor_helper_languages_go --> n_torsor_helper_languages_modules
    n_torsor_helper_languages_go --> n_torsor_helper_models
    n_torsor_helper_languages_javascript --> n_torsor_helper_languages_modules
    n_torsor_helper_languages_javascript --> n_torsor_helper_models
    n_torsor_helper_languages_python --> n_torsor_helper_languages_modules
    n_torsor_helper_languages_python --> n_torsor_helper_models
    n_torsor_helper_operations__shared --> n_torsor_helper_embeddings
    n_torsor_helper_operations__shared --> n_torsor_helper_indexer
    n_torsor_helper_operations__shared --> n_torsor_helper_store
    n_torsor_helper_operations_capture --> n_torsor_helper_operations__state
    n_torsor_helper_operations_capture --> n_torsor_helper_operations_decisions
    n_torsor_helper_operations_capture --> n_torsor_helper_operations_graph
    n_torsor_helper_operations_capture --> n_torsor_helper_operations_maintenance
    n_torsor_helper_operations_capture --> n_torsor_helper_operations_memory
    n_torsor_helper_operations_commands --> n_torsor_helper_models
    n_torsor_helper_operations_commands --> n_torsor_helper_store
    n_torsor_helper_operations_decisions --> n_torsor_helper_budget
    n_torsor_helper_operations_decisions --> n_torsor_helper_models
    n_torsor_helper_operations_gate --> n_torsor_helper_budget
    n_torsor_helper_operations_gate --> n_torsor_helper_operations__shared
    n_torsor_helper_operations_gate --> n_torsor_helper_operations_commands
    n_torsor_helper_operations_gate --> n_torsor_helper_operations_maintenance
    n_torsor_helper_operations_graph --> n_torsor_helper_budget
    n_torsor_helper_operations_graph --> n_torsor_helper_config
    n_torsor_helper_operations_graph --> n_torsor_helper_indexer
    n_torsor_helper_operations_graph --> n_torsor_helper_models
    n_torsor_helper_operations_graph --> n_torsor_helper_operations__shared
    n_torsor_helper_operations_graph --> n_torsor_helper_paths
    n_torsor_helper_operations_graph --> n_torsor_helper_store
    n_torsor_helper_operations_hooks_ops --> n_torsor_helper_operations_capture
    n_torsor_helper_operations_hooks_ops --> n_torsor_helper_operations_decisions
    n_torsor_helper_operations_maintenance --> n_torsor_helper_coach_state
    n_torsor_helper_operations_maintenance --> n_torsor_helper_indexer
    n_torsor_helper_operations_maintenance --> n_torsor_helper_models
    n_torsor_helper_operations_maintenance --> n_torsor_helper_operations__shared
    n_torsor_helper_operations_maintenance --> n_torsor_helper_operations__state
    n_torsor_helper_operations_maintenance --> n_torsor_helper_paths
    n_torsor_helper_operations_memory --> n_torsor_helper_budget
    n_torsor_helper_operations_memory --> n_torsor_helper_config
    n_torsor_helper_operations_memory --> n_torsor_helper_models
    n_torsor_helper_operations_memory --> n_torsor_helper_operations__shared
    n_torsor_helper_operations_memory --> n_torsor_helper_recall
    n_torsor_helper_operations_memory --> n_torsor_helper_search
    n_torsor_helper_operations_memory --> n_torsor_helper_store
    n_torsor_helper_operations_prompt_blocks --> n_torsor_helper_budget
    n_torsor_helper_operations_prompt_blocks --> n_torsor_helper_config
    n_torsor_helper_operations_prompt_blocks --> n_torsor_helper_operations__shared
    n_torsor_helper_operations_prompt_blocks --> n_torsor_helper_operations_commands
    n_torsor_helper_operations_prompt_blocks --> n_torsor_helper_store
    n_torsor_helper_practices --> n_torsor_helper_cartographer
    n_torsor_helper_recall --> n_torsor_helper_budget
    n_torsor_helper_recall --> n_torsor_helper_models
    n_torsor_helper_recall --> n_torsor_helper_snippets
    n_torsor_helper_search --> n_torsor_helper_budget
    n_torsor_helper_search --> n_torsor_helper_models
    n_torsor_helper_search --> n_torsor_helper_snippets
    n_torsor_helper_server --> n_torsor_helper_budget
    n_torsor_helper_server --> n_torsor_helper_config
    n_torsor_helper_server --> n_torsor_helper_paths
    n_torsor_helper_server --> n_torsor_helper_store
    n_torsor_helper_store --> n_torsor_helper_models
    n_torsor_helper_store --> n_torsor_helper_paths
    n_torsor_helper_templates --> n_torsor_helper_paths
```
