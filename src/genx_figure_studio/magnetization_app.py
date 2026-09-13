"""Paste-and-edit magnetization studio, using the existing native webview shell."""
import base64
from io import BytesIO
from pathlib import Path
import re

import matplotlib as mpl
import numpy as np

from .app import save_figure
from .magnetization import STACK_DEFAULTS, STACK_LIMITS, plot_genx_magnetization
from .plotting import PLOT_LOCK

DEFAULTS = dict(**STACK_DEFAULTS, fe_thickness=14., mgo_thickness=17.,
                substrate_thickness=18., cap_thickness=25., field_angle=0., arrow_scale=1.15, dpi=600)
LIMITS = dict(**STACK_LIMITS, fe_thickness=(.01,10000), mgo_thickness=(0,10000),
              substrate_thickness=(0,10000), cap_thickness=(0,10000), field_angle=(-3600,3600),
              arrow_scale=(.01,1.5), dpi=(72,1200))


def parse_values(text, column=0):
    """Read numeric lists, GenX magn_ang rows, or an explicitly selected table column."""
    if not isinstance(text, str):
        raise ValueError('Paste values as text.')
    lines = [line.split('#',1)[0].strip() for line in text.strip().splitlines()]
    lines = [line for line in lines if line and line not in ('[',']')]
    if not lines:
        raise ValueError('Paste at least one angle.')
    labelled = [line for line in lines if re.search(r'magn_?ang',line,re.I)] if column == 0 else []
    selected = labelled or lines
    values = []
    for line in selected:
        if labelled:
            line = re.split(r'magn_?ang',line,maxsplit=1,flags=re.I)[1]
        tokens = [token for token in re.split(r'[\s,;\[\]()=]+',line) if token]
        if column:
            if column > len(tokens):
                raise ValueError(f'Column {column} is missing in: {line}')
            tokens = [tokens[column-1]]
        elif labelled:
            tokens = tokens[:1]
        elif len(selected)>1 and len(tokens)>1 and not any(c in text for c in '[],;'):
            raise ValueError('Multiple table columns detected. Select the angle column explicitly.')
        try:
            row = [float(token.rstrip('°')) for token in tokens]
        except ValueError:
            if column and not values and line == selected[0]:
                continue  # Optional first header row in an explicitly selected table.
            raise ValueError(f'Could not read numbers in: {line}') from None
        values.extend(row)
    if not values or not np.isfinite(values).all():
        raise ValueError('Provide finite numeric values; NaN and infinity are not allowed.')
    if len(values)>60:
        raise ValueError('At most 60 Fe layers can be displayed in one figure.')
    return values


class MagnetizationAPI:
    def __init__(self, angles=None, moments=None):
        self._window = None
        self._angles = angles
        self._moments = moments

    def bootstrap(self):
        return dict(settings=DEFAULTS, limits=LIMITS,
                    angles='\n'.join(map(str,self._angles)) if self._angles is not None else '',
                    moments='\n'.join(map(str,self._moments)) if self._moments is not None else '')

    def _render(self, payload, extension, preview=False):
        if extension not in ('svg','pdf','png'):
            raise ValueError('Choose PDF, SVG or PNG.')
        column=int(payload.get('column',0))
        if not 0<=column<=20:
            raise ValueError('Column must be between 1 and 20, or use Auto.')
        angles=parse_values(payload.get('angles',''),column)
        moment_text=payload.get('moments','').strip()
        moments=parse_values(moment_text) if moment_text else None
        if moments is not None and len(moments)==1:
            moments=moments*len(angles)
        if payload.get('reverse',False):
            angles.reverse()
            if moments is not None:
                moments.reverse()
        settings={**DEFAULTS,**payload.get('settings',{})}
        for key,(low,high) in LIMITS.items():
            if key=='height' and settings[key] in ('',None):
                continue
            try:
                value=float(settings[key])
            except (ValueError,TypeError):
                raise ValueError(f'{key} must be a number.') from None
            if not np.isfinite(value) or not low<=value<=high:
                raise ValueError(f'{key} must be between {low} and {high}.')
            settings[key]=value
        if not float(settings['dpi']).is_integer():
            raise ValueError('DPI must be a whole number.')
        params={key:settings[key] for key in ('fe_thickness','mgo_thickness','substrate_thickness','cap_thickness','field_angle','arrow_scale')}
        height=float(settings['height']) if settings['height'] not in ('',None) else max(5.2,.61*len(angles)+2)
        if extension=='png' and settings['width']*height*settings['dpi']**2>40_000_000:
            raise ValueError('PNG exceeds 40 megapixels. Reduce size/DPI or choose PDF/SVG.')
        with PLOT_LOCK:
            fig=plot_genx_magnetization(angles,moments,**params,options=settings,show=False)
            buffer=BytesIO()
            with mpl.rc_context({'pdf.fonttype':42,'svg.fonttype':'path' if preview else 'none'}):
                fig.savefig(buffer,format=extension,dpi=settings['dpi'] if extension=='png' else 100,
                            facecolor=settings['background_color'])
        return buffer.getvalue(), dict(angles=angles,moments=moments,width=settings['width'],height=height)

    def preview(self,payload):
        try:
            content,info=self._render(payload,'svg',True)
            return dict(image='data:image/svg+xml;base64,'+base64.b64encode(content).decode(),**info)
        except (ValueError,TypeError,KeyError,OSError) as exc:
            return dict(error=str(exc))

    def export(self,payload,extension):
        try:
            content,_=self._render(payload,extension)
            return save_figure(self._window,content,extension,'magnetization')
        except (ValueError,TypeError,KeyError,OSError) as exc:
            return dict(error=str(exc))


def main(angles=None,moments=None):
    import webview
    api=MagnetizationAPI(angles,moments)
    assets=Path(__file__).with_name('ui')
    html=(assets/'magnetization.html').read_text()
    html=html.replace('/* STUDIO_CSS */',(assets/'style.css').read_text())
    html=html.replace('/* MAGNETIZATION_JS */',(assets/'magnetization.js').read_text())
    api._window=webview.create_window('GenX Magnetization Studio',html=html,js_api=api,
                                    width=1440,height=940,min_size=(1060,700),text_select=True)
    webview.start()


if __name__=='__main__':
    main()
