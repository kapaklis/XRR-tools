"""Paste interpretation and figure export must preserve the fitted values."""
from io import BytesIO
import numpy as np
import pytest
from matplotlib.image import imread
from genx_figure_studio.magnetization_app import MagnetizationAPI, parse_values


def test_paste_lists_and_genx_tables():
    assert parse_values('[14.2, 70.5, -3.1]') == [14.2, 70.5, -3.1]
    assert parse_values('14.2°\n70.5\n-3.1 # Fe3') == [14.2, 70.5, -3.1]
    assert parse_values('Fe1.setMagn_ang\t14.2\tTrue\t0\t90\nFe1.setD 14 True 0 20\nFe2.setMagn_ang -3.1 True -90 90') == [14.2, -3.1]
    assert parse_values('Layer Angle Error\nFe1 14.2 0.5\nFe2 -3.1 0.2',2) == [14.2,-3.1]
    for text in ('1 0.5\n2 0.2', 'NaN', 'inf', '', 'bad', '1\n'*61):
        with pytest.raises(ValueError):
            parse_values(text)


def test_editor_settings_order_and_export(tmp_path):
    api=MagnetizationAPI([14.2,70.5],[2,1])
    assert api.bootstrap()['angles']=='14.2\n70.5'
    payload=dict(angles='14.2\n70.5',moments='2',reverse=True,
                 settings=dict(title='Fitted Fe moments',fe_color='#123456',show_field=False,
                               layer_labels='Bottom\nTop',width=5,height=6,dpi=100))
    svg,info=api._render(payload,'svg')
    assert info['angles']==[70.5,14.2] and info['moments']==[2,2]
    assert all(text in svg.decode() for text in ('Fitted Fe moments','#123456','Bottom','Top','70.5°'))
    assert 'H:' not in svg.decode()
    png,_=api._render(payload,'png')
    assert imread(BytesIO(png)).shape[:2]==(600,500)
    class Dialog:
        def create_file_dialog(self,kind,**kwargs):
            return str(tmp_path/kwargs['save_filename'])
    api._window=Dialog()
    for extension,signature in [('pdf',b'%PDF'),('svg',b'<?xml'),('png',b'\x89PNG')]:
        assert 'path' in api.export(payload,extension)
        assert (tmp_path/f'magnetization.{extension}').read_bytes().startswith(signature)
    for bad in [dict(opacity=2),dict(fe_color='invalid'),dict(layer_labels='only one'),dict(dpi=100.5),dict(show_field='false')]:
        assert 'error' in api.preview({**payload,'settings':bad})
    assert 'error' in api.preview({**payload,'moments':'-2'})
    assert 'error' in api.preview({**payload,'moments':'1\n2\n3'})
    assert 'error' in api.export(payload,'jpg')
    np.testing.assert_equal(api.bootstrap()['angles'],'14.2\n70.5')
