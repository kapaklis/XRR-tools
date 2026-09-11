#!/usr/bin/env python3
"""GenX Figure Studio: interactive plotting of GenX reflectometry exports."""
import os, re, tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import numpy as np
import matplotlib as mpl
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

COLORS=["#1f77b4","#d62728","#2ca02c","#9467bd","#ff7f0e","#8c564b"]
LABELS={"00":r"$R^{++}$","11":r"$R^{--}$","01":r"$R^{+-}$","10":r"$R^{-+}$"}

def read_genx_dat(path):
    name=os.path.splitext(os.path.basename(path))[0]
    with open(path,"r",encoding="utf-8",errors="ignore") as f:
        for line in f:
            if not line.startswith("#"): break
            m=re.search(r'Dataset\s+"([^"]+)"',line)
            if m: name=m.group(1)
    a=np.loadtxt(path,comments="#")
    if a.ndim==1:a=a.reshape(1,-1)
    if a.shape[1]<3: raise ValueError("Expected at least Q, simulated intensity and measured intensity columns")
    p=name.split("_"); ch=p[0] if p and p[0] in LABELS else ""
    return dict(path=os.path.abspath(path),name=name,channel=ch,condition=" ".join(p[1:]),q=a[:,0],sim=a[:,1],obs=a[:,2],err=a[:,3] if a.shape[1]>3 else np.zeros(len(a)))

class Row:
    def __init__(self,parent,app,d,i):
        self.app,self.data=app,d; self.frame=ttk.Frame(parent); self.on=tk.BooleanVar(value=True)
        self.label=tk.StringVar(value=LABELS.get(d["channel"],d["name"])); self.color=COLORS[i%len(COLORS)]
        self.marker=tk.StringVar(value="o"); self.line=tk.StringVar(value="-")
        ttk.Checkbutton(self.frame,variable=self.on,command=app.redraw).grid(row=0,column=0)
        ttk.Label(self.frame,text=os.path.basename(d["path"]),width=25).grid(row=0,column=1,sticky="w")
        ttk.Entry(self.frame,textvariable=self.label,width=14).grid(row=0,column=2,padx=2)
        self.cb=tk.Button(self.frame,text="   ",bg=self.color,width=3,command=self.pick); self.cb.grid(row=0,column=3,padx=2)
        m=ttk.Combobox(self.frame,textvariable=self.marker,values=["o","s","^","v","D",".","x","+"],width=3);m.grid(row=0,column=4);m.bind("<<ComboboxSelected>>",lambda e:app.redraw())
        l=ttk.Combobox(self.frame,textvariable=self.line,values=["-","--","-.",":"],width=3);l.grid(row=0,column=5);l.bind("<<ComboboxSelected>>",lambda e:app.redraw())
        ttk.Button(self.frame,text="Remove",command=self.remove).grid(row=0,column=6,padx=2)
        self.label.trace_add("write",lambda *_:app.schedule())
    def pick(self):
        c=colorchooser.askcolor(initialcolor=self.color,parent=self.frame)[1]
        if c:self.color=c;self.cb.configure(bg=c);self.app.redraw()
    def remove(self): self.frame.destroy();self.app.rows.remove(self);self.app.redraw()

class GenXFigureStudio(tk.Tk):
    def __init__(self):
        super().__init__();self.title("GenX Figure Studio");self.geometry("1380x860");self.minsize(1050,650);self.rows=[];self.job=None
        self.build_ui();self.defaults();self.redraw()
    def build_ui(self):
        pane=ttk.Panedwindow(self,orient=tk.HORIZONTAL);pane.pack(fill=tk.BOTH,expand=True)
        left=ttk.Frame(pane,padding=8);right=ttk.Frame(pane,padding=4);pane.add(left,weight=1);pane.add(right,weight=3)
        bar=ttk.Frame(left);bar.pack(fill=tk.X);ttk.Button(bar,text="Add GenX files",command=self.add).pack(side=tk.LEFT);ttk.Button(bar,text="Clear",command=self.clear).pack(side=tk.LEFT,padx=4)
        ttk.Label(left,text="Datasets",font=("",11,"bold")).pack(anchor="w",pady=(7,2));self.rows_frame=ttk.Frame(left);self.rows_frame.pack(fill=tk.X)
        s=ttk.LabelFrame(left,text="Figure settings",padding=7);s.pack(fill=tk.X,pady=8)
        self.vars={k:tk.StringVar() for k in ["scale","title","xlabel","ylabel","xmin","xmax","ymin","ymax","background","fontsize","markersize","linewidth","legendcols","width","height","dpi"]}
        fields=[("Y scale","scale",["log","linear"]),("Title","title",None),("X label","xlabel",None),("Y label","ylabel",None),("X min","xmin",None),("X max","xmax",None),("Y min","ymin",None),("Y max","ymax",None),("Background","background",None),("Font size","fontsize",None),("Marker size","markersize",None),("Line width","linewidth",None),("Legend cols","legendcols",None),("Width (in)","width",None),("Height (in)","height",None),("Export DPI","dpi",None)]
        for i,(lab,key,vals) in enumerate(fields):
            r=i//2;c=(i%2)*2;ttk.Label(s,text=lab).grid(row=r,column=c,sticky="w",padx=2,pady=2)
            w=ttk.Combobox(s,textvariable=self.vars[key],values=vals,width=12) if vals else ttk.Entry(s,textvariable=self.vars[key],width=14)
            w.grid(row=r,column=c+1,padx=2,pady=2);w.bind("<<ComboboxSelected>>",lambda e:self.redraw())
            self.vars[key].trace_add("write",lambda *_:self.schedule())
        self.errors=tk.BooleanVar(value=True);self.legend=tk.BooleanVar(value=True);self.grid=tk.BooleanVar(value=False);self.mask=tk.BooleanVar(value=True);self.clip=tk.BooleanVar(value=True)
        opts=ttk.Frame(left);opts.pack(fill=tk.X)
        for text,var in [("Error bars",self.errors),("Legend",self.legend),("Grid",self.grid),("Mask data below background",self.mask),("Clip fit to background",self.clip)]:ttk.Checkbutton(opts,text=text,variable=var,command=self.redraw).pack(anchor="w")
        pre=ttk.Frame(left);pre.pack(fill=tk.X,pady=5);ttk.Button(pre,text="Single column",command=lambda:self.preset("single")).pack(side=tk.LEFT);ttk.Button(pre,text="Double column",command=lambda:self.preset("double")).pack(side=tk.LEFT,padx=3);ttk.Button(pre,text="Presentation",command=lambda:self.preset("pres")).pack(side=tk.LEFT)
        ex=ttk.Frame(left);ex.pack(fill=tk.X);[ttk.Button(ex,text=x.upper(),command=lambda e=x:self.export(e)).pack(side=tk.LEFT,padx=2) for x in ("pdf","svg","png")]
        self.figure=Figure(figsize=(7.2,5.0));self.canvas=FigureCanvasTkAgg(self.figure,master=right);self.canvas.get_tk_widget().pack(fill=tk.BOTH,expand=True)
        self.status=tk.StringVar(value="Ready");ttk.Label(self,textvariable=self.status,anchor="w").pack(fill=tk.X)
    def defaults(self):
        d=dict(scale="log",title="",xlabel=r"$Q_z$ ($\AA^{-1}$)",ylabel="Reflectivity",xmin="",xmax="",ymin="1e-7",ymax="1",background="1e-6",fontsize="9",markersize="3.5",linewidth="1.5",legendcols="2",width="7.2",height="5.0",dpi="600")
        for k,v in d.items():self.vars[k].set(v)
    def f(self,k,default=None):
        try:return float(self.vars[k].get())
        except:return default
    def schedule(self):
        if self.job:self.after_cancel(self.job)
        self.job=self.after(200,self.redraw)
    def add(self):
        fs=filedialog.askopenfilenames(title="Select GenX exports",filetypes=[("GenX data","*.dat *.txt"),("All files","*.*")])
        for p in fs:
            try:r=Row(self.rows_frame,self,read_genx_dat(p),len(self.rows));r.frame.pack(fill=tk.X,pady=1);self.rows.append(r)
            except Exception as e:messagebox.showerror("Could not load file",f"{p}\n\n{e}")
        if self.rows:
            self.vars["xmin"].set(f"{min(np.nanmin(r.data['q']) for r in self.rows):.4g}");self.vars["xmax"].set(f"{max(np.nanmax(r.data['q']) for r in self.rows):.4g}")
        self.redraw()
    def clear(self):
        for r in self.rows:r.frame.destroy()
        self.rows=[];self.redraw()
    def preset(self,m):
        vals={"single":("3.35","2.75","8","2.7","1.1","1"),"double":("7.2","4.8","9","3.2","1.4","2"),"pres":("10","6.5","12","4.5","2.0","2")}[m]
        for k,v in zip(["width","height","fontsize","markersize","linewidth","legendcols"],vals):self.vars[k].set(v)
        self.redraw()
    def build(self,fig):
        fig.clear();ax=fig.add_subplot(111);rows=[r for r in self.rows if r.on.get()]
        if not rows:ax.text(.5,.5,"Load GenX .dat files to begin",ha="center",va="center",transform=ax.transAxes);ax.set_axis_off();return
        fs=self.f("fontsize",9);ms=self.f("markersize",3.5);lw=self.f("linewidth",1.5);bg=self.f("background",1e-6)
        mpl.rcParams.update({"font.size":fs,"xtick.direction":"in","ytick.direction":"in","xtick.top":True,"ytick.right":True})
        for r in rows:
            d=r.data;mask=(d["obs"]>=bg) if self.mask.get() and self.vars["scale"].get()=="log" else np.isfinite(d["obs"])
            if self.errors.get():ax.errorbar(d["q"][mask],d["obs"][mask],yerr=d["err"][mask],fmt=r.marker.get(),linestyle="none",markersize=ms,markerfacecolor="none",color=r.color,elinewidth=.7,label=r.label.get())
            else:ax.plot(d["q"][mask],d["obs"][mask],linestyle="none",marker=r.marker.get(),markersize=ms,markerfacecolor="none",color=r.color,label=r.label.get())
            sim=np.maximum(d["sim"],bg) if self.clip.get() and self.vars["scale"].get()=="log" else d["sim"]
            ax.plot(d["q"],sim,r.line.get(),linewidth=lw,color=r.color,label="_nolegend_")
        ax.set_yscale(self.vars["scale"].get());ax.set_xlabel(self.vars["xlabel"].get());ax.set_ylabel(self.vars["ylabel"].get())
        xmin,xmax,ymin,ymax=[self.f(k) for k in ("xmin","xmax","ymin","ymax")]
        if xmin is not None or xmax is not None:ax.set_xlim(left=xmin,right=xmax)
        if ymin is not None or ymax is not None:ax.set_ylim(bottom=ymin,top=ymax)
        ax.grid(False,which="both")
        if self.grid.get():ax.grid(True,which="major",alpha=.25,linewidth=.6)
        if self.vars["title"].get().strip():ax.set_title(self.vars["title"].get())
        if self.legend.get():ax.legend(frameon=False,ncol=max(1,int(self.f("legendcols",2))))
        fig.tight_layout()
    def redraw(self):
        try:self.build(self.figure);self.canvas.draw();self.status.set("Preview updated")
        except Exception as e:self.status.set(f"Preview error: {e}")
    def export(self,ext):
        if not self.rows:return messagebox.showinfo("No data","Load at least one GenX file first.")
        p=filedialog.asksaveasfilename(defaultextension="."+ext,filetypes=[(ext.upper(),"*."+ext)])
        if not p:return
        f=Figure(figsize=(self.f("width",7.2),self.f("height",5)));self.build(f);kw={"bbox_inches":"tight"}
        if ext=="png":kw["dpi"]=int(self.f("dpi",600))
        f.savefig(p,**kw);self.status.set(f"Exported: {p}")

def main(): GenXFigureStudio().mainloop()
if __name__=="__main__":main()
