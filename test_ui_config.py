"""
Unit tests for UI configuration parsing and design tokens generation.
"""

import json
import tempfile
from pathlib import Path

import pytest

from app_spec_parser import (
    MCP_SUPPORTED_LIBRARIES,
    VALID_FRAMEWORKS,
    VALID_UI_LIBRARIES,
    VALID_VISUAL_STYLES,
    get_ui_config_from_spec,
    parse_section,
    parse_ui_components,
    parse_ui_config,
    parse_visual_style,
    parse_xml_value,
)
from design_tokens import (
    STYLE_PRESETS,
    generate_design_tokens,
    generate_design_tokens_from_spec,
    get_style_preset,
    validate_visual_style,
)

# =============================================================================
# Test: parse_section
# =============================================================================

class TestParseSection:
    """Tests for parse_section function."""

    def test_parse_simple_section(self):
        content = "<ui_components>test content</ui_components>"
        result = parse_section(content, "ui_components")
        assert result == "test content"

    def test_parse_section_with_whitespace(self):
        content = """
        <ui_components>
            test content
        </ui_components>
        """
        result = parse_section(content, "ui_components")
        assert result == "test content"

    def test_parse_section_with_attributes(self):
        content = '<ui_components version="1">test content</ui_components>'
        result = parse_section(content, "ui_components")
        assert result == "test content"

    def test_parse_missing_section(self):
        content = "<other_section>test</other_section>"
        result = parse_section(content, "ui_components")
        assert result is None

    def test_parse_empty_section(self):
        content = "<ui_components></ui_components>"
        result = parse_section(content, "ui_components")
        assert result == ""


# =============================================================================
# Test: parse_xml_value
# =============================================================================

class TestParseXmlValue:
    """Tests for parse_xml_value function."""

    def test_parse_simple_value(self):
        content = "<library>shadcn-ui</library>"
        result = parse_xml_value(content, "library")
        assert result == "shadcn-ui"

    def test_parse_value_with_whitespace(self):
        content = "<library>  shadcn-ui  </library>"
        result = parse_xml_value(content, "library")
        assert result == "shadcn-ui"

    def test_parse_missing_value(self):
        content = "<other>value</other>"
        result = parse_xml_value(content, "library")
        assert result is None

    def test_parse_empty_value(self):
        content = "<library></library>"
        result = parse_xml_value(content, "library")
        assert result is None  # Empty string stripped to None

    def test_parse_comment_only(self):
        content = "<library><!-- comment --></library>"
        result = parse_xml_value(content, "library")
        assert result is None


# =============================================================================
# Test: parse_ui_components
# =============================================================================

class TestParseUIComponents:
    """Tests for parse_ui_components function."""

    def test_parse_complete_ui_components(self):
        content = """
        <ui_components>
            <library>shadcn-ui</library>
            <framework>react</framework>
            <has_mcp>true</has_mcp>
        </ui_components>
        """
        result = parse_ui_components(content)
        assert result["library"] == "shadcn-ui"
        assert result["framework"] == "react"
        assert result["has_mcp"] is True

    def test_parse_ui_components_false_mcp(self):
        content = """
        <ui_components>
            <library>radix-ui</library>
            <framework>react</framework>
            <has_mcp>false</has_mcp>
        </ui_components>
        """
        result = parse_ui_components(content)
        assert result["library"] == "radix-ui"
        assert result["has_mcp"] is False

    def test_parse_ui_components_defaults(self):
        content = "<other>content</other>"
        result = parse_ui_components(content)
        assert result["library"] == "none"
        assert result["framework"] == "react"
        assert result["has_mcp"] is False

    def test_parse_ark_ui(self):
        content = """
        <ui_components>
            <library>ark-ui</library>
            <framework>vue</framework>
            <has_mcp>true</has_mcp>
        </ui_components>
        """
        result = parse_ui_components(content)
        assert result["library"] == "ark-ui"
        assert result["framework"] == "vue"
        assert result["has_mcp"] is True


# =============================================================================
# Test: parse_visual_style
# =============================================================================

class TestParseVisualStyle:
    """Tests for parse_visual_style function."""

    def test_parse_complete_visual_style(self):
        content = """
        <visual_style>
            <style>neobrutalism</style>
            <design_tokens_path>.autocoder/design-tokens.json</design_tokens_path>
        </visual_style>
        """
        result = parse_visual_style(content)
        assert result["style"] == "neobrutalism"
        assert result["design_tokens_path"] == ".autocoder/design-tokens.json"

    def test_parse_visual_style_default(self):
        content = """
        <visual_style>
            <style>default</style>
        </visual_style>
        """
        result = parse_visual_style(content)
        assert result["style"] == "default"
        assert result["design_tokens_path"] == ""

    def test_parse_visual_style_missing(self):
        content = "<other>content</other>"
        result = parse_visual_style(content)
        assert result["style"] == "default"
        assert result["design_tokens_path"] == ""


# =============================================================================
# Test: parse_ui_config
# =============================================================================

class TestParseUIConfig:
    """Tests for parse_ui_config function."""

    def test_parse_complete_config(self):
        content = """
        <ui_components>
            <library>shadcn-ui</library>
            <framework>react</framework>
            <has_mcp>true</has_mcp>
        </ui_components>
        <visual_style>
            <style>neobrutalism</style>
            <design_tokens_path>.autocoder/design-tokens.json</design_tokens_path>
        </visual_style>
        """
        result = parse_ui_config(content)
        assert result["library"] == "shadcn-ui"
        assert result["framework"] == "react"
        assert result["has_mcp"] is True
        assert result["style"] == "neobrutalism"
        assert result["design_tokens_path"] == ".autocoder/design-tokens.json"

    def test_parse_empty_config(self):
        content = ""
        result = parse_ui_config(content)
        assert result["library"] == "none"
        assert result["framework"] == "react"
        assert result["has_mcp"] is False
        assert result["style"] == "default"


# =============================================================================
# Test: get_ui_config_from_spec
# =============================================================================

class TestGetUIConfigFromSpec:
    """Tests for get_ui_config_from_spec function."""

    def test_get_config_from_existing_spec(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            prompts_dir = project_dir / "prompts"
            prompts_dir.mkdir()

            spec_content = """
            <project_specification>
                <ui_components>
                    <library>ark-ui</library>
                    <framework>solid</framework>
                    <has_mcp>true</has_mcp>
                </ui_components>
                <visual_style>
                    <style>glassmorphism</style>
                </visual_style>
            </project_specification>
            """
            (prompts_dir / "app_spec.txt").write_text(spec_content)

            result = get_ui_config_from_spec(project_dir)
            assert result is not None
            assert result["library"] == "ark-ui"
            assert result["framework"] == "solid"
            assert result["has_mcp"] is True
            assert result["style"] == "glassmorphism"

    def test_get_config_missing_spec(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            result = get_ui_config_from_spec(project_dir)
            assert result is None


# =============================================================================
# Test: STYLE_PRESETS
# =============================================================================

class TestStylePresets:
    """Tests for style presets in design_tokens.py."""

    def test_neobrutalism_preset_exists(self):
        assert "neobrutalism" in STYLE_PRESETS
        preset = STYLE_PRESETS["neobrutalism"]
        assert preset["borders"]["width"] == "4px"
        assert preset["borders"]["radius"] == "0"
        assert "4px 4px 0 0" in preset["shadows"]["default"]

    def test_glassmorphism_preset_exists(self):
        assert "glassmorphism" in STYLE_PRESETS
        preset = STYLE_PRESETS["glassmorphism"]
        assert preset["borders"]["radius"] == "16px"
        assert preset["effects"]["backdropBlur"] == "12px"

    def test_retro_preset_exists(self):
        assert "retro" in STYLE_PRESETS
        preset = STYLE_PRESETS["retro"]
        assert preset["colors"]["primary"] == "#ff00ff"
        assert preset["colors"]["secondary"] == "#00ffff"
        assert "Press Start 2P" in preset["typography"]["fontFamily"]


# =============================================================================
# Test: get_style_preset
# =============================================================================

class TestGetStylePreset:
    """Tests for get_style_preset function."""

    def test_get_neobrutalism_preset(self):
        preset = get_style_preset("neobrutalism")
        assert preset is not None
        assert "borders" in preset
        assert "shadows" in preset

    def test_get_default_preset(self):
        preset = get_style_preset("default")
        assert preset is None

    def test_get_unknown_preset(self):
        preset = get_style_preset("unknown_style")
        assert preset is None


# =============================================================================
# Test: generate_design_tokens
# =============================================================================

class TestGenerateDesignTokens:
    """Tests for generate_design_tokens function."""

    def test_generate_neobrutalism_tokens(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            result = generate_design_tokens(project_dir, "neobrutalism")

            assert result is not None
            assert result.exists()
            assert result.name == "design-tokens.json"

            tokens = json.loads(result.read_text())
            assert tokens["borders"]["width"] == "4px"

    def test_generate_default_tokens(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            result = generate_design_tokens(project_dir, "default")
            assert result is None

    def test_generate_custom_tokens(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            result = generate_design_tokens(project_dir, "custom")
            assert result is None


# =============================================================================
# Test: generate_design_tokens_from_spec
# =============================================================================

class TestGenerateDesignTokensFromSpec:
    """Tests for generate_design_tokens_from_spec function."""

    def test_generate_tokens_from_neobrutalism_spec(self):
        """Integration test: generate tokens from a spec file with neobrutalism style."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            prompts_dir = project_dir / "prompts"
            prompts_dir.mkdir()

            spec_content = """
            <project_specification>
                <visual_style>
                    <style>neobrutalism</style>
                    <design_tokens_path>.autocoder/design-tokens.json</design_tokens_path>
                </visual_style>
            </project_specification>
            """
            (prompts_dir / "app_spec.txt").write_text(spec_content)

            result = generate_design_tokens_from_spec(project_dir)

            assert result is not None
            assert result.exists()
            assert result.name == "design-tokens.json"

            tokens = json.loads(result.read_text())
            assert tokens["borders"]["width"] == "4px"
            assert tokens["borders"]["radius"] == "0"

    def test_generate_tokens_from_default_spec(self):
        """No tokens generated for default style."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            prompts_dir = project_dir / "prompts"
            prompts_dir.mkdir()

            spec_content = """
            <project_specification>
                <visual_style>
                    <style>default</style>
                </visual_style>
            </project_specification>
            """
            (prompts_dir / "app_spec.txt").write_text(spec_content)

            result = generate_design_tokens_from_spec(project_dir)
            assert result is None

    def test_generate_tokens_missing_spec(self):
        """Returns None when spec file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            result = generate_design_tokens_from_spec(project_dir)
            assert result is None


# =============================================================================
# Test: validate_visual_style
# =============================================================================

class TestValidateVisualStyle:
    """Tests for validate_visual_style function."""

    def test_valid_styles(self):
        assert validate_visual_style("default") is True
        assert validate_visual_style("neobrutalism") is True
        assert validate_visual_style("glassmorphism") is True
        assert validate_visual_style("retro") is True
        assert validate_visual_style("custom") is True

    def test_invalid_styles(self):
        assert validate_visual_style("unknown") is False
        assert validate_visual_style("") is False
        assert validate_visual_style("NEOBRUTALISM") is False  # Case sensitive


# =============================================================================
# Test: Constants
# =============================================================================

class TestConstants:
    """Tests for module constants."""

    def test_valid_ui_libraries(self):
        assert "shadcn-ui" in VALID_UI_LIBRARIES
        assert "ark-ui" in VALID_UI_LIBRARIES
        assert "radix-ui" in VALID_UI_LIBRARIES
        assert "none" in VALID_UI_LIBRARIES

    def test_mcp_supported_libraries(self):
        assert "shadcn-ui" in MCP_SUPPORTED_LIBRARIES
        assert "ark-ui" in MCP_SUPPORTED_LIBRARIES
        assert "radix-ui" not in MCP_SUPPORTED_LIBRARIES
        assert "none" not in MCP_SUPPORTED_LIBRARIES

    def test_valid_visual_styles(self):
        assert "default" in VALID_VISUAL_STYLES
        assert "neobrutalism" in VALID_VISUAL_STYLES
        assert "glassmorphism" in VALID_VISUAL_STYLES
        assert "retro" in VALID_VISUAL_STYLES
        assert "custom" in VALID_VISUAL_STYLES

    def test_valid_frameworks(self):
        assert "react" in VALID_FRAMEWORKS
        assert "vue" in VALID_FRAMEWORKS
        assert "solid" in VALID_FRAMEWORKS
        assert "svelte" in VALID_FRAMEWORKS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
