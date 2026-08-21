import pytest
from gui.src.theming.schema import BackgroundAssetRef, BackgroundTokens, ThemePack, ThemeSchemaError
from gui.src.theming.storage import (
    import_asset,
    list_saved_theme_packs,
    load_theme_pack,
    missing_assets,
    resolve_asset_path,
    save_theme_pack,
    theme_pack_from_dict,
    theme_pack_to_dict,
)


def _sample_pack(**overrides) -> ThemePack:
    kwargs = dict(name="My Theme", base="dark", color_overrides={"accent": "#ff00ff"})
    kwargs.update(overrides)
    return ThemePack(**kwargs)


class TestRoundTrip:
    def test_minimal_pack_round_trips(self):
        pack = _sample_pack()
        data = theme_pack_to_dict(pack)
        restored = theme_pack_from_dict(data)
        assert restored == pack

    def test_pack_with_backgrounds_round_trips(self):
        bg = BackgroundTokens(
            images=(BackgroundAssetRef(kind="linked", path="/tmp/bg.png"),),
            opacity=0.5,
            blur_px=10,
            fit_mode="contain",
            rotation_interval_sec=300,
        )
        pack = _sample_pack(backgrounds=(bg,))
        restored = theme_pack_from_dict(theme_pack_to_dict(pack))
        assert restored == pack
        assert restored.backgrounds[0].images[0].path == "/tmp/bg.png"

    def test_wrong_schema_marker_rejected(self):
        data = theme_pack_to_dict(_sample_pack())
        data["schema"] = "something-else"
        with pytest.raises(ThemeSchemaError):
            theme_pack_from_dict(data)


class TestSaveLoad:
    def test_save_then_load(self, tmp_path, monkeypatch):
        import gui.src.theming.storage as storage_mod

        monkeypatch.setattr(storage_mod, "THEME_PACKS_DIR", tmp_path / "packs")
        pack = _sample_pack(name="Sunset Glass")
        path = save_theme_pack(pack)
        assert path.exists()
        assert path.name == "sunset-glass.json"
        loaded = load_theme_pack(path)
        assert loaded == pack

    def test_explicit_path_overrides_default(self, tmp_path):
        pack = _sample_pack()
        path = tmp_path / "custom.json"
        result = save_theme_pack(pack, path=path)
        assert result == path
        assert load_theme_pack(path) == pack

    def test_list_saved_theme_packs(self, tmp_path, monkeypatch):
        import gui.src.theming.storage as storage_mod

        monkeypatch.setattr(storage_mod, "THEME_PACKS_DIR", tmp_path / "packs")
        assert list_saved_theme_packs() == []
        save_theme_pack(_sample_pack(name="A"))
        save_theme_pack(_sample_pack(name="B"))
        names = [p.name for p in list_saved_theme_packs()]
        assert names == ["a.json", "b.json"]


class TestAssetManagement:
    def test_import_asset_copies_and_returns_content_hashed_id(self, tmp_path, monkeypatch):
        import gui.src.theming.storage as storage_mod

        monkeypatch.setattr(storage_mod, "THEME_ASSETS_DIR", tmp_path / "assets")
        source = tmp_path / "wallpaper.png"
        source.write_bytes(b"fake-png-bytes")

        asset_id = import_asset(source)
        assert asset_id.endswith(".png")
        assert (tmp_path / "assets" / asset_id).read_bytes() == b"fake-png-bytes"

    def test_importing_same_bytes_twice_is_idempotent(self, tmp_path, monkeypatch):
        import gui.src.theming.storage as storage_mod

        monkeypatch.setattr(storage_mod, "THEME_ASSETS_DIR", tmp_path / "assets")
        source = tmp_path / "wallpaper.png"
        source.write_bytes(b"same-bytes")

        id1 = import_asset(source)
        id2 = import_asset(source)
        assert id1 == id2
        assert len(list((tmp_path / "assets").iterdir())) == 1

    def test_resolve_asset_path_linked(self, tmp_path):
        real_file = tmp_path / "bg.jpg"
        real_file.write_bytes(b"x")
        ref = BackgroundAssetRef(kind="linked", path=str(real_file))
        assert resolve_asset_path(ref) == real_file

    def test_resolve_asset_path_linked_missing(self, tmp_path):
        ref = BackgroundAssetRef(kind="linked", path=str(tmp_path / "does-not-exist.jpg"))
        assert resolve_asset_path(ref) is None

    def test_resolve_asset_path_imported(self, tmp_path, monkeypatch):
        import gui.src.theming.storage as storage_mod

        monkeypatch.setattr(storage_mod, "THEME_ASSETS_DIR", tmp_path / "assets")
        (tmp_path / "assets").mkdir()
        (tmp_path / "assets" / "abc.png").write_bytes(b"x")
        ref = BackgroundAssetRef(kind="imported", asset_id="abc.png")
        assert resolve_asset_path(ref) == tmp_path / "assets" / "abc.png"

    def test_resolve_asset_path_imported_missing(self, tmp_path, monkeypatch):
        import gui.src.theming.storage as storage_mod

        monkeypatch.setattr(storage_mod, "THEME_ASSETS_DIR", tmp_path / "assets")
        ref = BackgroundAssetRef(kind="imported", asset_id="nope.png")
        assert resolve_asset_path(ref) is None


class TestMissingAssets:
    def test_no_backgrounds_no_missing(self):
        assert missing_assets(_sample_pack()) == []

    def test_reports_missing_linked_file(self, tmp_path):
        ref = BackgroundAssetRef(kind="linked", path=str(tmp_path / "gone.png"))
        bg = BackgroundTokens(images=(ref,))
        pack = _sample_pack(backgrounds=(bg,))
        assert missing_assets(pack) == [ref]

    def test_present_asset_not_reported(self, tmp_path):
        real_file = tmp_path / "present.png"
        real_file.write_bytes(b"x")
        ref = BackgroundAssetRef(kind="linked", path=str(real_file))
        bg = BackgroundTokens(images=(ref,))
        pack = _sample_pack(backgrounds=(bg,))
        assert missing_assets(pack) == []
