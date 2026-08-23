import pytest

from gui.src.theming.schema import (
    BackgroundAssetRef,
    BackgroundTokens,
    ColorTokens,
    CornerTokens,
    ThemePack,
    ThemeSchemaError,
    TypographyTokens,
)


class TestColorTokens:
    def test_valid_hex_colors_ok(self):
        ColorTokens(
            accent="#00bcd4", surface="#2d2d30", window_bg="#1e1e1e",
            text="#cccccc", muted_text="#888888", border="#3e3e3e",
        )

    @pytest.mark.parametrize("bad", ["00bcd4", "#00bcd", "#gggggg", "", "red", "#0000000"])
    def test_invalid_hex_rejected(self, bad):
        with pytest.raises(ThemeSchemaError):
            ColorTokens(accent=bad, surface="#fff", window_bg="#fff", text="#fff", muted_text="#fff", border="#fff")


class TestTypographyTokens:
    def test_default_is_valid(self):
        TypographyTokens()

    @pytest.mark.parametrize("scale", [79, 151, -10, 0])
    def test_scale_out_of_range_rejected(self, scale):
        with pytest.raises(ThemeSchemaError):
            TypographyTokens(scale_percent=scale)

    def test_invalid_weight_rejected(self):
        with pytest.raises(ThemeSchemaError):
            TypographyTokens(weight="ultrabold")


class TestCornerTokens:
    def test_negative_radius_rejected(self):
        with pytest.raises(ThemeSchemaError):
            CornerTokens(radius_px=-1)


class TestBackgroundAssetRef:
    def test_linked_requires_path(self):
        with pytest.raises(ThemeSchemaError):
            BackgroundAssetRef(kind="linked")

    def test_imported_requires_asset_id(self):
        with pytest.raises(ThemeSchemaError):
            BackgroundAssetRef(kind="imported")

    def test_invalid_kind_rejected(self):
        with pytest.raises(ThemeSchemaError):
            BackgroundAssetRef(kind="embedded", path="/x.png")

    def test_linked_ok(self):
        ref = BackgroundAssetRef(kind="linked", path="/home/user/bg.png")
        assert ref.path == "/home/user/bg.png"

    def test_imported_ok(self):
        ref = BackgroundAssetRef(kind="imported", asset_id="abc123.png")
        assert ref.asset_id == "abc123.png"


class TestBackgroundTokens:
    def test_defaults_are_valid(self):
        bg = BackgroundTokens()
        assert bg.opacity == 1.0
        assert bg.blur_px == 0
        assert bg.rotation_interval_sec == 0

    @pytest.mark.parametrize("opacity", [0.05, 1.01, -1])
    def test_opacity_out_of_range_rejected(self, opacity):
        with pytest.raises(ThemeSchemaError):
            BackgroundTokens(opacity=opacity)

    def test_blur_out_of_range_rejected(self):
        with pytest.raises(ThemeSchemaError):
            BackgroundTokens(blur_px=31)

    def test_invalid_fit_mode_rejected(self):
        with pytest.raises(ThemeSchemaError):
            BackgroundTokens(fit_mode="stretch")

    def test_invalid_rotation_interval_rejected(self):
        with pytest.raises(ThemeSchemaError):
            BackgroundTokens(rotation_interval_sec=42)

    def test_valid_rotation_intervals_accepted(self):
        for sec in (0, 60, 300, 900, 3600):
            BackgroundTokens(rotation_interval_sec=sec)


class TestThemePack:
    def test_minimal_valid_pack(self):
        pack = ThemePack(name="My Theme")
        assert pack.base == "dark"
        assert pack.color_overrides == {}

    def test_empty_name_rejected(self):
        with pytest.raises(ThemeSchemaError):
            ThemePack(name="   ")

    def test_invalid_base_rejected(self):
        with pytest.raises(ThemeSchemaError):
            ThemePack(name="x", base="sepia")

    def test_unknown_override_key_rejected(self):
        with pytest.raises(ThemeSchemaError):
            ThemePack(name="x", color_overrides={"not_a_token": "#ffffff"})

    def test_invalid_override_value_rejected(self):
        with pytest.raises(ThemeSchemaError):
            ThemePack(name="x", color_overrides={"accent": "blue"})

    def test_sparse_overrides_is_the_point(self):
        # Base+override-delta model: only changed tokens are stored.
        pack = ThemePack(name="x", base="dark", color_overrides={"accent": "#ff00ff"})
        assert pack.color_overrides == {"accent": "#ff00ff"}

    def test_wrong_schema_version_rejected(self):
        with pytest.raises(ThemeSchemaError):
            ThemePack(name="x", schema_version=999)
