"""Noidea24 fork (beta): the Battle style choice in an adventure's settings."""
from pathlib import Path

import pytest


@pytest.mark.parametrize('width', [320, 1280])
def test_battle_style_saves_and_reloads(page, tmp_path, monkeypatch, width):
    from playwright.sync_api import expect
    from conftest import serve
    from pokesim.app.manager import Manager, create_app
    from pokesim.app.registry import identifier
    captured = {}

    def factory(url):
        manager = Manager(tmp_path / 'library', url)
        monkeypatch.setattr(manager, 'start', lambda: None)
        manager.registry.add_rom('fixture', 'sha1', 'yellow')
        row = manager.registry.create('Weekend Yellow', 'fixture', {}, identifier())
        captured.update(manager=manager, row=row)
        return create_app(manager)
    with serve(factory) as url:
        page.set_viewport_size({'width': width, 'height': 900})
        page.goto(url)
        page.locator('[data-action="settings"]').click()
        style = page.locator('#settings-battle-profile')
        expect(style).to_have_value('balanced')
        expect(page.locator('#settings-profile-note')).to_contain_text('The original')
        expect(page.locator('#settings-profile-custom')).to_be_hidden()
        style.select_option('bold')
        expect(page.locator('#settings-profile-note')).to_contain_text('30 game minutes')
        page.get_by_role('button', name='Save adventure settings', exact=True).click()
        expect(page.locator('#adventure-settings')).not_to_be_visible()
        settings = lambda: captured['manager'].registry.adventure(captured['row']['id'])['settings']
        assert settings()['battle_profile'] == 'bold'
        page.locator('[data-action="settings"]').click()
        expect(style).to_have_value('bold')
        style.select_option('custom')
        expect(page.locator('#settings-profile-custom')).to_be_visible()
        page.locator('#settings-training-patience').fill('20')
        page.locator('#settings-gym-caution').fill('50')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        folder = Path('/tmp/pokesim-profile-ui')
        folder.mkdir(exist_ok=True)
        page.locator('#adventure-settings').screenshot(path=str(folder / f'custom-{width}.png'))
        page.get_by_role('button', name='Save adventure settings', exact=True).click()
        expect(page.locator('#adventure-settings')).not_to_be_visible()
        assert {k: settings()[k] for k in ('battle_profile', 'gym_caution', 'level_margin', 'training_patience')} == {
            'battle_profile': 'custom', 'gym_caution': 50, 'level_margin': 10, 'training_patience': 20}
        page.locator('[data-action="settings"]').click()
        style.select_option('balanced')
        page.get_by_role('button', name='Save adventure settings', exact=True).click()
        expect(page.locator('#adventure-settings')).not_to_be_visible()
        assert not {'battle_profile', 'gym_caution', 'level_margin', 'training_patience'} & set(settings())
