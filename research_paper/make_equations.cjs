"use strict";

const fs = require("fs");
const sharp = require("sharp");
const { mathjax } = require("mathjax-full/js/mathjax.js");
const { TeX } = require("mathjax-full/js/input/tex.js");
const { SVG } = require("mathjax-full/js/output/svg.js");
const { liteAdaptor } = require("mathjax-full/js/adaptors/liteAdaptor.js");
const { RegisterHTMLHandler } = require("mathjax-full/js/handlers/html.js");
const { AllPackages } = require("mathjax-full/js/input/tex/AllPackages.js");

const adaptor = liteAdaptor();
RegisterHTMLHandler(adaptor);
const tex = new TeX({ packages: AllPackages });
const svgOut = new SVG({ fontCache: "local" });
const doc = mathjax.document("", { InputJax: tex, OutputJax: svgOut });

async function render(latex, out) {
  const html = adaptor.outerHTML(doc.convert(latex, { display: true }));
  const a = html.indexOf("<svg");
  const b = html.indexOf("</svg>");
  let svg = html.slice(a, b + 6)
    .replace(/currentColor/g, "#000000")
    .replace(/<svg /, '<svg xmlns="http://www.w3.org/2000/svg" ');
  await sharp(Buffer.from(svg), { density: 360 })
    .png()
    .toFile(out);
}

Promise.all([
  render(String.raw`P(r,s)=\bigwedge_{c\in C_s}c(r),\qquad A_s(r)=\bigvee_{j=1}^{m}\bigwedge_{c\in C_{s,j}}c(r)`, "research_paper/equation_1.png"),
  render(String.raw`V(r,s)=\begin{cases}\mathrm{Ineligible},&P=0\\\mathrm{Needs\ Review},&P=1\land(U\lor M)\\\mathrm{Missing\ Documents},&P=1\land\neg(U\lor M)\land D=0\\\mathrm{Eligible},&P=1\land\neg(U\lor M)\land D=1\end{cases}`, "research_paper/equation_2.png"),
  render(String.raw`\mathcal{C}_u=\{k\in K\mid \operatorname{scope}(k)\subseteq\operatorname{perm}(u)\},\qquad S(q,k)=\frac{e(q)\cdot e(k)}{\lVert e(q)\rVert\,\lVert e(k)\rVert}`, "research_paper/equation_3.png"),
]).catch((err) => { console.error(err); process.exit(1); });
