'use strict';
const $ = id => document.getElementById(id);
const groups = [
  ['Titles & labels', 'title:Figure title','subtitle:Subtitle','layer_prefix:Layer prefix','layer_labels:Custom layer labels (one per layer, substrate first)','substrate_label:Substrate label','cap_label:Cap label','field_label:Field label','moment_label:Moment symbol','moment_units:Moment units'],
  ['Colors','fe_color:Fe layers','mgo_color:MgO spacers','arrow_color:Moment arrows','angle_color:Angles','field_color:Field arrow','text_color:Other text','substrate_color:Substrate','cap_color:Cap','background_color:Background','edge_color:Layer edges','guide_color:Guide lines'],
  ['Arrows & visibility','arrow_scale:Moment length scale','arrow_width:Moment line width (pt)','head_size:Arrowhead size (pt)','dot_size:Origin marker size (pt)','field_angle:Field angle (°)','field_length:Field arrow length','field_width:Field line width (pt)','opacity:Layer opacity','edge_width:Layer edge width (pt)','show_angles:Show angles','show_moments:Show magnitudes','show_layers:Show layer labels','show_guides:Show guide lines','show_field:Show applied field'],
  ['Typography','font:Typeface','fontsize:Layer font size (pt)','title_size:Title size (pt)','angle_size:Angle size (pt)','moment_size:Magnitude size (pt)','note_size:Footnote size (pt)','angle_decimals:Angle decimal places'],
  ['Layout & projection','width:Width (in)','height:Height (in, blank = auto)','label_x:Right label position','fe_height:Fe schematic height','spacer_height:Spacer schematic height','depth_x:Projection horizontal offset','depth_y:Projection vertical offset','x_slope:Projection tilt'],
  ['Structure & footnotes','fe_thickness:Fe thickness (Å)','mgo_thickness:MgO thickness (Å)','substrate_thickness:Substrate thickness (0 = hide)','cap_thickness:Cap thickness (0 = hide)','thickness_note:Thickness note ({fe} and {mgo})','angle_note:Angle convention note','moment_note:Magnitude note'],
  ['Raster export','dpi:PNG resolution (DPI)']
];
let defaults, limits, revision = 0, timer, rendering = false, valid = false, exporting = false, zoom = 1, ratio = 1;
function exportState() { for (const id of ['export','export-top']) $(id).disabled = !valid || exporting; }
function payload() {
  const settings = {};
  for (const input of $('settings').elements) settings[input.name] = input.type === 'checkbox' ? input.checked : input.value;
  return {angles:$('angles').value,moments:$('moments').value,column:Number($('column').value),reverse:$('order').value==='top',settings};
}
function fit() {
  const area=$('canvas-area');
  $('paper').style.width = Math.max(160, Math.min(area.clientWidth-60,(area.clientHeight-48)*ratio))*zoom+'px';
}
function queue() {
  revision++; valid=false; exportState(); $('paper').classList.add('stale');
  clearTimeout(timer); timer=setTimeout(render,250);
}
async function render() {
  if (rendering) return;
  rendering=true;
  const current=revision;
  $('status').textContent='Rendering…';
  try {
    const result=await window.pywebview.api.preview(payload());
    if (current!==revision) return;
    if (result.error) throw new Error(result.error);
    $('figure-image').src=result.image; $('figure-image').hidden=false; $('figure-empty').hidden=true;
    $('count').textContent=result.angles.length+' layers';
    $('parsed').textContent=result.angles.map((v,i)=>`Fe${i+1}: ${v}°${result.moments ? ' · m = '+result.moments[i] : ''}`).join('\n');
    $('figure-size').textContent=`${(result.width*25.4).toFixed(1)} × ${(result.height*25.4).toFixed(1)} mm`;
    ratio=result.width/result.height; fit();
    $('error').hidden=true; $('paper').classList.remove('stale'); valid=true;
    $('status').textContent='Preview ready';
  } catch(error) {
    if(current===revision) { $('error').textContent=error.message; $('error').hidden=false; $('status').textContent='Check input or figure settings'; }
  } finally {
    rendering=false; exportState();
    if(current!==revision) render();
  }
}
function controls() {
  $('settings').replaceChildren();
  for (const [index, [title,...fields]] of groups.entries()) {
    const detail=document.createElement('details'); detail.open=index===0;
    const summary=document.createElement('summary'); summary.textContent=title; detail.append(summary);
    const section=document.createElement('div'); section.className='section-content'; detail.append(section);
    for (const field of fields) {
      const [key,labelText]=field.split(':');
      const label=document.createElement('label'); label.textContent=labelText;
      let input=document.createElement(key==='layer_labels' || key.endsWith('_note') ? 'textarea' : key==='font' ? 'select' : 'input');
      input.name=key;
      if(key==='font') for(const name of ['DejaVu Sans','DejaVu Serif']) input.add(new Option(name,name));
      else if(typeof defaults[key]==='boolean') { input.type='checkbox'; label.className='toggle'; }
      else if(key.endsWith('_color')) input.type='color';
      else if(limits[key]) { input.type='number'; [input.min,input.max]=limits[key]; input.step=['dpi','angle_decimals'].includes(key)?'1':'any'; if(key==='height') input.placeholder='Auto'; }
      if(input.type==='checkbox') { input.checked=defaults[key]; label.prepend(input); }
      else { input.value=defaults[key]; label.append(input); }
      section.append(label);
    }
    $('settings').append(detail);
  }
}
async function save() {
  if(!valid || exporting) return;
  exporting=true; exportState(); $('status').textContent='Exporting…';
  try {
    const result=await window.pywebview.api.export(payload(),$('export-format').value);
    if(result.error) throw new Error(result.error);
    $('status').textContent=result.cancelled?'Export cancelled':'Saved '+result.path;
  } catch(error) { $('error').textContent=error.message; $('error').hidden=false; $('status').textContent='Export failed'; }
  finally { exporting=false; exportState(); }
}
window.addEventListener('pywebviewready',async()=>{
  try {
    const data=await window.pywebview.api.bootstrap(); defaults=data.settings; limits=data.limits;
    controls(); $('angles').value=data.angles; $('moments').value=data.moments;
    for(let i=1;i<=20;i++) $('column').add(new Option('Column '+i,i));
    for(const id of ['angles','moments','column','order','settings']) $(id).addEventListener('input',queue);
    $('settings').addEventListener('submit',event=>event.preventDefault());
    $('reset').disabled=false; $('reset').onclick=()=>{ controls(); queue(); };
    $('export-format').onchange=()=>{ for(const id of ['export','export-top']) $(id).textContent='Export '+$('export-format').value.toUpperCase()+' ↗'; };
    $('export').onclick=save; $('export-top').onclick=save;
    $('zoom-in').onclick=()=>{zoom=Math.min(4,zoom*1.25);fit();};
    $('zoom-out').onclick=()=>{zoom=Math.max(.5,zoom/1.25);fit();};
    $('zoom-fit').onclick=()=>{zoom=1;fit();}; window.addEventListener('resize',fit);
    if(data.angles) queue(); else $('status').textContent='Paste angles from GenX to begin';
  } catch(error) { $('error').textContent=error.message; $('error').hidden=false; }
});
