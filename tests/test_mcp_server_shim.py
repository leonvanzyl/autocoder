def test_mcp_server_feature_module_imports():
    import mcp_server.feature_mcp as mod

    assert hasattr(mod, "mcp")

