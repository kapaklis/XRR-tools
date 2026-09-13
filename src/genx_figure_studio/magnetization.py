"""Depth-aligned Fe/MgO magnetization figures from fitted GenX parameters."""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import is_color_like
from matplotlib.figure import Figure
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle, Polygon


STACK_DEFAULTS = dict(
    title='Fe/MgO magnetization', subtitle='', width=5.6, height='', font='DejaVu Sans',
    fontsize=10, title_size=15, angle_size=12, moment_size=8, note_size=8,
    fe_color='#F04B3E', mgo_color='#477DDD', substrate_color='#8F999C', cap_color='#959595',
    arrow_color='#AD0808', field_color='#666666', text_color='#555555', angle_color='#980808',
    edge_color='#FFFFFF', guide_color='#C9CDD0', background_color='#FFFFFF',
    opacity=.28, edge_width=.6, arrow_width=2.8, head_size=15, dot_size=3.5,
    field_width=2.3, field_length=1.3, layer_prefix='Fe', substrate_label='MgO substrate',
    cap_label='Cap', field_label='H', moment_label='m', moment_units='', angle_decimals=1,
    show_angles=True, show_moments=True, show_layers=True, show_guides=True, show_field=True,
    label_x=1.94, fe_height=.74, spacer_height=.30, depth_x=.48, depth_y=.34, x_slope=-.10,
    thickness_note='Fe {fe} Å / MgO {mgo} Å · layer thicknesses schematic',
    angle_note='Angles measured from +x; Fe1 is substrate-adjacent.',
    moment_note='In-plane arrow lengths scale with moment; magnitudes retain input units.',
    layer_labels='',
)
STACK_LIMITS = dict(width=(3,20), height=(3,30), fontsize=(5,24), title_size=(5,32),
    angle_size=(5,24), moment_size=(5,24), note_size=(5,20), opacity=(0,1),
    edge_width=(0,3), arrow_width=(.2,8), head_size=(4,30), dot_size=(0,10),
    field_width=(.2,8), field_length=(.2,2), angle_decimals=(0,6), label_x=(1.6,4),
    fe_height=(.5,2), spacer_height=(0,1.5), depth_x=(-.8,.8), depth_y=(.1,.65), x_slope=(-.3,.3))


def validate_stack_options(options):
    settings = {**STACK_DEFAULTS, **(options or {})}
    for key, default in STACK_DEFAULTS.items():
        if isinstance(default, bool) and not isinstance(settings[key], bool):
            raise ValueError(f'{key} must be on or off')
        if isinstance(default, str) and key != 'height' and not isinstance(settings[key], str):
            raise ValueError(f'{key} must be text')
    for key, (low, high) in STACK_LIMITS.items():
        if key == 'height' and settings[key] in ('', None):
            settings[key] = None
            continue
        try:
            value = float(settings[key])
        except (TypeError, ValueError):
            raise ValueError(f'{key} must be a number') from None
        if not np.isfinite(value) or not low <= value <= high:
            raise ValueError(f'{key} must be between {low} and {high}')
        settings[key] = value
    if not settings['angle_decimals'].is_integer():
        raise ValueError('Angle decimal places must be a whole number')
    settings['angle_decimals'] = int(settings['angle_decimals'])
    for key, value in settings.items():
        if key.endswith('_color') and not is_color_like(value):
            raise ValueError(f'Invalid color for {key}')
    if settings['font'] not in ('DejaVu Sans', 'DejaVu Serif'):
        raise ValueError('Choose DejaVu Sans or DejaVu Serif')
    return settings


def plot_genx_magnetization(
    angles, moments=None, fe_thickness=14.0, mgo_thickness=17.0,
    substrate_thickness=18.0, cap_thickness=25.0, field_angle=0.0,
    arrow_scale=1.0, save=None, *, show=True, view="stack", options=None,
):
    """Plot fitted directions as a translucent stack or a depth-aligned profile.

    view="stack" uses a fixed oblique projection inspired by Figure 3 of
    Phys. Rev. B 97, 174424 (2018). Layer thicknesses are schematic in this
    view; view="profile" retains the quantitative depth-aligned panels.

    Fe1 is substrate-adjacent. Angles are degrees counterclockwise from +x,
    as in the original script; field_angle uses the same reference. The field
    does not rotate the fitted angles. Depth and thicknesses are in angstroms.
    Arrow lengths share one normalization (largest supplied moment = 1).
    Moment values are shown in the supplied units; no conversion is applied.
    With moments=None, arrows indicate direction only. Widths are schematic.
    Returns the Figure; use show=False for batch exports.
    """
    angles = np.asarray(angles, dtype=float)
    if angles.ndim != 1 or not angles.size or not np.isfinite(angles).all():
        raise ValueError("angles must be a nonempty one-dimensional array of finite values")
    supplied_moments = moments is not None
    moments = np.ones_like(angles) if moments is None else np.asarray(moments, dtype=float)
    if moments.shape != angles.shape or not np.isfinite(moments).all() or (moments < 0).any():
        raise ValueError("moments must match angles and contain finite, nonnegative magnitudes")
    dimensions = np.asarray([fe_thickness, mgo_thickness, substrate_thickness, cap_thickness], dtype=float)
    if not np.isfinite(dimensions).all() or (dimensions < 0).any() or fe_thickness <= 0:
        raise ValueError("Thicknesses must be finite and nonnegative; Fe thickness must be positive")
    if not np.isfinite(field_angle) or not np.isfinite(arrow_scale) or not 0 < arrow_scale <= 1.5:
        raise ValueError("field_angle must be finite and arrow_scale must be in (0, 1.5]")

    if view not in ("stack", "profile"):
        raise ValueError("view must be 'stack' or 'profile'")
    if view == "stack":
        return _plot_stack(angles, moments, supplied_moments, fe_thickness,
                           mgo_thickness, substrate_thickness, cap_thickness,
                           field_angle, arrow_scale, save, show, options)

    count = len(angles)
    period = fe_thickness + mgo_thickness
    centres = substrate_thickness + np.arange(count) * period + fe_thickness / 2
    cap_bottom = substrate_thickness + count * period
    total = cap_bottom + cap_thickness
    normalized = moments / moments.max() if moments.max() > 0 else np.zeros_like(moments)
    fe_color, mgo_color, ink, field_color = '#DCEAF2', '#F2F4F5', '#00689D', '#9A5518'
    style = {'font.size': 10, 'font.family': 'DejaVu Sans', 'axes.linewidth': .7,
             'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none'}
    with plt.rc_context(style):
        fig = plt.figure(figsize=(9.0, max(5.4, .68 * count + 2.1)))
        stack, vectors, profile = fig.subplots(1, 3, gridspec_kw={'width_ratios': [1.05, 1.7, 1.5]})
        fig.subplots_adjust(left=.09, right=.96, bottom=.12, top=.85, wspace=.22)
        fig.suptitle('Layer-resolved magnetization', x=.09, ha='left', y=.975, fontsize=17, fontweight='bold')
        fig.text(.09, .938, 'Fe/MgO superlattice · GenX fit', fontsize=11, color='#596570')
        fig.text(.09, .902, r'Angles: counterclockwise from $+x$ in the film plane', fontsize=10)
        for ax, title in zip((stack, vectors, profile), ('Layer stack', 'In-plane moments', 'Fitted angle')):
            ax.set_ylim(0, total)
            ax.set_title(title, loc='left', fontsize=11, pad=13)
        stack.set_xlim(0, 1)
        stack.set_xticks([])
        stack.set_ylabel(r'Depth from substrate base ($\AA$)')
        stack.spines[['top', 'right', 'bottom']].set_visible(False)
        stack.tick_params(axis='y', length=3, color='#8A969F')
        stack.add_patch(Rectangle((.1, 0), .8, substrate_thickness, facecolor='#D9DDDF', edgecolor='white'))
        if substrate_thickness:
            stack.text(.5, substrate_thickness / 2, 'MgO substrate', ha='center', va='center', fontsize=8)
        for i, centre in enumerate(centres):
            bottom = centre - fe_thickness / 2
            stack.add_patch(Rectangle((.1, bottom), .8, fe_thickness, facecolor=fe_color, edgecolor='#91B2C7', lw=.5))
            stack.text(.5, centre, f'Fe{i + 1}', color=ink, ha='center', va='center', fontsize=9, fontweight='bold')
            stack.add_patch(Rectangle((.1, bottom + fe_thickness), .8, mgo_thickness, facecolor=mgo_color, edgecolor='white', lw=.6))
        if cap_thickness:
            stack.add_patch(Rectangle((.1, cap_bottom), .8, cap_thickness, facecolor='#E3E0DB', edgecolor='white'))
            stack.text(.5, cap_bottom + cap_thickness / 2, 'Cap', ha='center', va='center', fontsize=9)
        vectors.set_xlim(0, 1)
        vectors.set_axis_off()
        # Each glyph has its own equal-aspect xy axes: depth scaling cannot distort an angle.
        glyph_height = min(.94 * period / total, .28)
        for i, (centre, angle, length) in enumerate(zip(centres, angles, normalized)):
            y = centre / total
            vectors.axhline(centre, color='#E8EDF0', lw=.6, zorder=0)
            glyph = vectors.inset_axes([.02, y - glyph_height / 2, .44, glyph_height])
            glyph.set(xlim=(-1.65, 1.65), ylim=(-1.65, 1.65), aspect='equal')
            glyph.set_axis_off()
            glyph.add_patch(Circle((0, 0), 1.05, fill=False, ec='#D5DEE5', lw=.7))
            glyph.plot([-1.2, 1.2], [0, 0], color='#D5DEE5', lw=.6)
            glyph.plot([0, 0], [-1.2, 1.2], color='#D5DEE5', lw=.6)
            h = np.deg2rad(field_angle)
            glyph.add_patch(FancyArrowPatch((0, 0), (1.3 * np.cos(h), 1.3 * np.sin(h)),
                arrowstyle='->', mutation_scale=8, lw=1.0, linestyle='--', color=field_color, zorder=2))
            if length > 0:
                phi = np.deg2rad(angle)
                glyph.add_patch(FancyArrowPatch((0, 0), (arrow_scale * length * np.cos(phi), arrow_scale * length * np.sin(phi)),
                    arrowstyle='-|>', mutation_scale=13, lw=2.5, color=ink, shrinkA=0, shrinkB=0, zorder=4))
            glyph.plot(0, 0, 'o', ms=2.7, color=ink, zorder=5)
            vectors.text(.52, y, f'{angle:g}°', transform=vectors.transAxes, va='bottom', fontsize=12, color=ink, fontweight='bold')
            magnitude = f'm = {moments[i]:g}' if supplied_moments else 'direction only'
            if length == 0:
                magnitude += ' · no moment'
            vectors.text(.52, y, magnitude, transform=vectors.transAxes, va='top', fontsize=9, color='#596570')
        profile.plot(angles, centres, '-', color='#9EBACB', lw=1, zorder=2)
        profile.scatter(angles, centres, s=38, facecolor='white', edgecolor=ink, linewidth=1.5, zorder=3)
        profile.set_xlabel(r'Fitted angle $\theta$ (deg)')
        profile.set_yticks(centres, labels=[])
        profile.grid(axis='y', color='#E8EDF0', lw=.7)
        profile.spines[['top', 'right', 'left']].set_visible(False)
        profile.tick_params(axis='y', length=0)
        profile.tick_params(axis='x', length=3)
        profile.margins(x=.15)
        fig.text(.09, .055, f'Blue arrows: Fe moments   ·   Dashed amber arrows: H = {field_angle:g}°', fontsize=9, color='#43515D')
        fig.text(.09, .029, 'Arrow lengths scaled to the largest moment; values retain the supplied units. MgO spacers shown in light grey.'
                 if supplied_moments else 'Equal arrow lengths indicate direction only. MgO spacers shown in light grey.', fontsize=8, color='#596570')
        if save is not None:
            fig.savefig(save, dpi=600, facecolor='white')
    if show:
        plt.show()
    return fig


def _project_plane(x, y, z, depth_x=.48, depth_y=.34, x_slope=-.10):
    """Oblique projection of the film plane and stack depth."""
    return np.array([x + depth_x * y, z + x_slope * x + depth_y * y])


def _plot_stack(angles, moments, supplied_moments, fe_thickness,
                mgo_thickness, substrate_thickness, cap_thickness,
                field_angle, arrow_scale, save, show, options=None):
    """Vector schematic with editable artwork and explicit painter order."""
    s = validate_stack_options(options)
    n = len(angles)
    normalized = moments / moments.max() if moments.max() else np.zeros_like(moments)
    names = s['layer_labels'].splitlines() if s['layer_labels'].strip() else [f"{s['layer_prefix']}{i+1}" for i in range(n)]
    if len(names) != n:
        raise ValueError('Provide one layer label per angle, or leave layer labels empty')
    def project(x, y, z):
        return _project_plane(x, y, z, s['depth_x'], s['depth_y'], s['x_slope'])
    style = {'font.family': s['font'], 'font.size': s['fontsize'], 'text.color': s['text_color'],
             'pdf.fonttype': 42, 'svg.fonttype': 'none'}
    with plt.rc_context(style):
        # Headless API calls must not create pyplot-managed windows on worker threads.
        if show:
            fig = plt.figure(figsize=(s['width'], s['height'] or max(5.2, .61*n+2)))
        else:
            fig = Figure(figsize=(s['width'], s['height'] or max(5.2, .61*n+2)))
        fig.set_facecolor(s['background_color'])
        ax = fig.add_subplot()
        fig.subplots_adjust(left=.05, right=.98, bottom=.11, top=.88)
        ax.set_aspect('equal')
        ax.set_axis_off()
        fe_height, spacer_height = s['fe_height'], s['spacer_height'] if mgo_thickness else 0
        substrate_height = .42 if substrate_thickness else 0
        cap_height = .30 if cap_thickness else 0
        total = substrate_height + n*(fe_height+spacer_height) + cap_height
        ax.set_xlim(-2.3, s['label_x']+1.8)
        ax.set_ylim(-1.0, total+1.35)
        fig.suptitle(s['title'], fontsize=s['title_size'], y=.965)
        fig.text(.5, .925, s['subtitle'], ha='center', fontsize=s['fontsize'])

        def block(z, height, color):
            a, b, c, d = [(-1,-1),(1,-1),(1,1),(-1,1)]
            for corners, levels, alpha in [
                ([a,b,c,d],[z]*4,.64),
                ([b,c,c,b],[z,z,z+height,z+height],.89),
                ([a,b,b,a],[z,z,z+height,z+height],1),
                ([a,b,c,d],[z+height]*4,.79),
            ]:
                points = [project(x,y,level) for (x,y),level in zip(corners,levels)]
                ax.add_patch(Polygon(points, facecolor=color, edgecolor=s['edge_color'],
                    linewidth=s['edge_width'], alpha=alpha*s['opacity'], zorder=1+z/(total+1)))

        if substrate_height:
            block(0,substrate_height,s['substrate_color'])
        centres=[]
        z=substrate_height
        for i in range(n):
            centres.append(z+fe_height/2)
            block(z,fe_height,s['fe_color'])
            z+=fe_height
            if spacer_height:
                block(z,spacer_height,s['mgo_color'])
                z+=spacer_height
        if cap_height:
            block(z,cap_height,s['cap_color'])
        for i,(angle,moment,centre) in enumerate(zip(angles,normalized,centres)):
            phi=np.deg2rad(angle)
            vector=arrow_scale*moment*np.array([np.cos(phi),np.sin(phi)])
            tail,tip=project(*(-vector/2),centre),project(*(vector/2),centre)
            if moment>0:
                ax.add_patch(FancyArrowPatch(tail,tip,arrowstyle='-|>',color=s['arrow_color'],
                    linewidth=s['arrow_width'],mutation_scale=s['head_size'],shrinkA=0,shrinkB=0,zorder=20))
            ax.plot(*tail,'o',color=s['arrow_color'],ms=s['dot_size'],zorder=21)
            if s['show_layers']:
                ax.text(-1.88,centre,names[i],ha='right',va='center',fontsize=s['fontsize'])
            if s['show_guides']:
                ax.plot([1.49,s['label_x']-.14],[centre,centre],color=s['guide_color'],lw=.65,zorder=22)
            if s['show_angles']:
                label = f"{angle:.{s['angle_decimals']}f}°" if options else f'{angle:g}°'
                ax.text(s['label_x'],centre+.06,label,va='bottom',color=s['angle_color'],fontsize=s['angle_size'],fontweight='bold')
            if supplied_moments and s['show_moments']:
                label=f"{s['moment_label']} = {moments[i]:g}" + (f" {s['moment_units']}" if s['moment_units'] else '')
                ax.text(s['label_x'],centre+.02,label+(' (zero)' if moment==0 else ''),va='top',fontsize=s['moment_size'])
        if substrate_height:
            ax.text(0,-.70,s['substrate_label'],ha='center',fontsize=s['fontsize'])
        if cap_height:
            ax.text(s['label_x'],total-cap_height/2,s['cap_label'],fontsize=s['fontsize'])
        if s['show_field']:
            h=np.deg2rad(field_angle)
            hvector=s['field_length']*np.array([np.cos(h),np.sin(h)])
            hcentre=total+.75
            ax.add_patch(FancyArrowPatch(project(*(-hvector/2),hcentre),project(*(hvector/2),hcentre),
                arrowstyle='-|>',mutation_scale=s['head_size'],lw=s['field_width'],color=s['field_color'],zorder=25))
            ax.text(s['label_x'],hcentre,f"{s['field_label']}: {field_angle:g}°",va='center',fontsize=s['fontsize'],color=s['field_color'])
        for y,key in ((.070,'thickness_note'),(.042,'angle_note'),(.015,'moment_note')):
            note=s[key].replace('{fe}',f'{fe_thickness:g}').replace('{mgo}',f'{mgo_thickness:g}')
            if key=='moment_note' and not supplied_moments and note==STACK_DEFAULTS[key]:
                note='Equal arrow lengths indicate direction only.'
            fig.text(.5,y,note,ha='center',fontsize=s['note_size'])
        if save:
            fig.savefig(save,dpi=600,facecolor=s['background_color'])
    if show:
        plt.show()
    return fig
