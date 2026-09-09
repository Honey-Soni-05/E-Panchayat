/**
 * GIS map — every facility, sanctioned work and located complaint the API holds
 * for this Gram Panchayat, plotted at its own recorded coordinates.
 *
 * What changed from the mock version:
 *
 * - The three layers came from GIS_FACILITIES, PROJECTS and GRIEVANCES in
 *   mockData. They now come from /facilities, /projects and /grievances.
 * - MAP_CENTER was the constant [18.4907, 73.9806] with "(Loni Kalbhor, Pune)"
 *   printed beside it, so every village's map opened over the same field. The
 *   centre is now the signed-in officer's own village from /villages/current.
 *   An administrator has no village and that endpoint returns null, so the map
 *   falls back to fitting the bounds of whatever was actually plotted.
 * - A grievance's latitude and longitude are nullable. Complaints without them
 *   are left off the map and counted in a note under it, rather than being
 *   dropped at the village centre where they would read as a real location.
 *
 * Colour alone does not identify a layer here. Each one has its own outline
 * shape as well as its own colour and icon, so a reader with a colour-vision
 * deficiency can still tell a project pin from a grievance pin, and the legend
 * shows the same marker artwork the map uses rather than a colour swatch.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import L from 'leaflet';
import { Layers, CheckSquare, Square, Loader2, Info } from 'lucide-react';

import {
  api,
  type Facility,
  type Grievance,
  type Project,
  type Village,
} from '../lib/api';
import { useQuery } from '../lib/useApi';
import { EmptyState, ErrorNotice } from './schemes/SchemeBits';

// ─── Layer definitions ──────────────────────────────────────────────────────

type LayerKey = 'project' | 'grievance' | 'water' | 'school' | 'health' | 'other';
type Shape = 'circle' | 'square' | 'triangle' | 'diamond' | 'hexagon' | 'pentagon';

interface LayerStyle {
  shape: Shape;
  color: string;
  glyph: string;
  /** Existing translation key, or null when the screen has none yet. */
  i18nKey: string | null;
  labelEn: string;
  labelMr: string;
}

/** One table drives the markers, the legend and the toggles, so the three
 *  cannot drift apart and show a reader a key that the map does not use. */
const LAYERS: Record<LayerKey, LayerStyle> = {
  project: {
    shape: 'diamond',
    color: '#b45309',
    glyph: '🏗️',
    i18nKey: 'gis_page.projects',
    labelEn: 'Projects',
    labelMr: 'प्रकल्प',
  },
  grievance: {
    shape: 'hexagon',
    color: '#b91c1c',
    glyph: '⚠️',
    i18nKey: 'gis_page.grievances',
    labelEn: 'Grievances',
    labelMr: 'तक्रारी',
  },
  water: {
    shape: 'triangle',
    color: '#0f766e',
    glyph: '🚰',
    i18nKey: 'gis_page.water',
    labelEn: 'Water facilities',
    labelMr: 'पाणी सुविधा',
  },
  school: {
    shape: 'square',
    color: '#2547a8',
    glyph: '🏫',
    i18nKey: 'gis_page.schools',
    labelEn: 'Schools',
    labelMr: 'शाळा',
  },
  health: {
    shape: 'circle',
    color: '#7c3aed',
    glyph: '🏥',
    i18nKey: 'gis_page.health',
    labelEn: 'Health facilities',
    labelMr: 'आरोग्य सुविधा',
  },
  other: {
    shape: 'pentagon',
    color: '#475569',
    glyph: '📍',
    i18nKey: null,
    labelEn: 'Other facilities',
    labelMr: 'इतर सुविधा',
  },
};

const LAYER_ORDER: LayerKey[] = ['project', 'grievance', 'water', 'school', 'health', 'other'];

const SHAPES: Record<Shape, string> = {
  circle: '<circle cx="15" cy="15" r="12.5" />',
  square: '<rect x="2.5" y="2.5" width="25" height="25" rx="4" />',
  triangle: '<polygon points="15,2 28,27 2,27" />',
  diamond: '<polygon points="15,1.5 28.5,15 15,28.5 1.5,15" />',
  hexagon: '<polygon points="15,1.5 27,8.5 27,21.5 15,28.5 3,21.5 3,8.5" />',
  pentagon: '<polygon points="15,1.5 28.5,11.5 23.5,27.5 6.5,27.5 1.5,11.5" />',
};

/** Built only from the constants above — no record data reaches this markup. */
const markerHtml = (style: LayerStyle): string =>
  `<span style="position:relative;display:block;width:30px;height:30px;filter:drop-shadow(0 1px 2px rgba(15,23,42,.35))">` +
  `<svg viewBox="0 0 30 30" width="30" height="30" style="display:block" aria-hidden="true">` +
  `<g fill="#ffffff" stroke="${style.color}" stroke-width="3" stroke-linejoin="round">${SHAPES[style.shape]}</g>` +
  `</svg>` +
  `<span style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:13px;line-height:1">${style.glyph}</span>` +
  `</span>`;

const iconFor = (key: LayerKey): L.DivIcon =>
  L.divIcon({
    html: markerHtml(LAYERS[key]),
    className: 'epanchayat-gis-marker',
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    popupAnchor: [0, -15],
  });

const facilityLayer = (facilityType: string): LayerKey => {
  const normalised = (facilityType || '').toLowerCase();
  if (normalised === 'water') return 'water';
  if (normalised === 'school') return 'school';
  if (normalised === 'health') return 'health';
  // An unrecognised type is still a real facility, so it is shown under its
  // own key rather than being silently discarded.
  return 'other';
};

// ─── Popup markup ───────────────────────────────────────────────────────────

const HTML_ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

/** Complaint titles and descriptions are written by residents, so every
 *  record value is escaped before it goes into popup HTML. */
const esc = (value: string): string => value.replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);

const popupHtml = (
  style: LayerStyle,
  kicker: string,
  title: string,
  rows: { label: string; value: string }[],
  note?: string,
): string => {
  const rowsHtml = rows
    .map(
      (r) =>
        `<div style="display:flex;gap:6px;justify-content:space-between;font-size:11px;line-height:1.5">` +
        `<span style="color:#64748b">${esc(r.label)}</span>` +
        `<strong style="color:#0f172a;text-align:right">${esc(r.value)}</strong></div>`,
    )
    .join('');

  return (
    `<div style="min-width:190px;font-family:inherit">` +
    `<span style="display:inline-block;font-size:9px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:${style.color};border:1px solid ${style.color}40;background:${style.color}12;padding:1px 6px;border-radius:4px">${esc(kicker)}</span>` +
    `<strong style="display:block;font-size:13px;color:#0f172a;margin:6px 0 6px;line-height:1.3">${esc(title)}</strong>` +
    `<div style="border-top:1px solid #e2e8f0;padding-top:6px;display:flex;flex-direction:column;gap:2px">${rowsHtml}</div>` +
    (note
      ? `<p style="margin:6px 0 0;font-size:11px;color:#475569;line-height:1.5">${esc(note)}</p>`
      : '') +
    `</div>`
  );
};

// ─── Helpers ────────────────────────────────────────────────────────────────

const pick = (en: string, mr: string | null | undefined, isEnglish: boolean) =>
  isEnglish ? en : mr || en;

const hasCoords = (lat: number | null, lng: number | null): boolean =>
  lat !== null && lng !== null && Number.isFinite(lat) && Number.isFinite(lng);

const lakhs = (rupees: number, isEnglish: boolean) =>
  isEnglish
    ? `₹${(rupees / 100000).toFixed(2)} lakh`
    : `₹${(rupees / 100000).toFixed(2)} लाख`;

const formatDate = (value: string, isEnglish: boolean) =>
  new Date(value).toLocaleDateString(isEnglish ? 'en-IN' : 'mr-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });

// ─── Screen ─────────────────────────────────────────────────────────────────

export const GISMap: React.FC = () => {
  const { t, i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';

  const facilities = useQuery<Facility[]>(() => api.facilities.list(), []);
  const projects = useQuery<Project[]>(() => api.projects.list(), []);
  const grievances = useQuery<Grievance[]>(() => api.grievances.list(), []);
  const village = useQuery<Village | null>(() => api.villages.current(), []);

  const [enabled, setEnabled] = useState<Record<LayerKey, boolean>>({
    project: true,
    grievance: true,
    water: true,
    school: true,
    health: true,
    other: true,
  });

  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const groupRef = useRef<L.LayerGroup | null>(null);
  // The opening view is set once. Re-fitting on every layer toggle would yank
  // the map away from wherever the officer had panned it.
  const viewAppliedRef = useRef(false);
  const [mapReady, setMapReady] = useState(false);
  // The basemap failing is not the same as the records failing, and the screen
  // has to be able to say which. Markers are drawn from our own API and stay
  // correct even when no tile arrives.
  const [tilesBroken, setTilesBroken] = useState(false);

  const facilityRows = useMemo(() => facilities.data ?? [], [facilities.data]);
  const projectRows = useMemo(() => projects.data ?? [], [projects.data]);
  const grievanceRows = useMemo(() => grievances.data ?? [], [grievances.data]);

  /** Records that carry usable coordinates, split by layer. */
  const plottable = useMemo(() => {
    const facilitiesOk = facilityRows.filter((f) => hasCoords(f.latitude, f.longitude));
    const projectsOk = projectRows.filter((p) => hasCoords(p.latitude, p.longitude));
    const grievancesOk = grievanceRows.filter((g) => hasCoords(g.latitude, g.longitude));
    return { facilitiesOk, projectsOk, grievancesOk };
  }, [facilityRows, projectRows, grievanceRows]);

  /** How many records exist but cannot be placed. Shown, not hidden. */
  const unmapped = useMemo(
    () => ({
      facilities: facilityRows.length - plottable.facilitiesOk.length,
      projects: projectRows.length - plottable.projectsOk.length,
      grievances: grievanceRows.length - plottable.grievancesOk.length,
    }),
    [facilityRows, projectRows, grievanceRows, plottable],
  );

  const layerCounts = useMemo(() => {
    const counts: Record<LayerKey, number> = {
      project: plottable.projectsOk.length,
      grievance: plottable.grievancesOk.length,
      water: 0,
      school: 0,
      health: 0,
      other: 0,
    };
    for (const f of plottable.facilitiesOk) counts[facilityLayer(f.facilityType)] += 1;
    return counts;
  }, [plottable]);

  /** Every plotted point regardless of the toggles — the fallback view has to
   *  be stable even if the officer has switched a layer off. */
  const allPoints = useMemo<[number, number][]>(() => {
    const points: [number, number][] = [];
    for (const f of plottable.facilitiesOk) points.push([f.latitude, f.longitude]);
    for (const p of plottable.projectsOk) points.push([p.latitude, p.longitude]);
    for (const g of plottable.grievancesOk) {
      points.push([g.latitude as number, g.longitude as number]);
    }
    return points;
  }, [plottable]);

  const centre = useMemo<[number, number] | null>(() => {
    const v = village.data;
    if (v && v.latitude !== null && v.longitude !== null) return [v.latitude, v.longitude];
    return null;
  }, [village.data]);

  const dataLoading = facilities.loading || projects.loading || grievances.loading;
  // A village lookup that failed is not fatal — the map can still fit itself to
  // the plotted records — so it is reported without blocking the screen.
  const dataError = facilities.error || projects.error || grievances.error;
  const canShowMap = !dataLoading && !dataError && (centre !== null || allPoints.length > 0);

  const retryAll = () => {
    facilities.refetch();
    projects.refetch();
    grievances.refetch();
  };

  // Create the map only once there is somewhere honest to point it.
  useEffect(() => {
    if (!canShowMap) return;
    const element = containerRef.current;
    if (!element || mapRef.current) return;

    const map = L.map(element, { zoomControl: true, scrollWheelZoom: true });

    // OpenStreetMap's own tiles, which need no key and no account.
    //
    // This was CARTO's basemaps.cartocdn.com, which is where the map broke: it
    // kept answering 200 with a perfectly ordinary-looking tile that had
    // "API KEY REQUIRED" written diagonally across it. Nothing failed, nothing
    // logged, and the map rendered — just with the watermark repeated over
    // every tile. CARTO now wants a registered key for their basemaps.
    //
    // OSM is the right replacement for this project rather than another free
    // tier: the licence is unambiguous, attribution is the only requirement,
    // and there is no account to lapse before a viva. Their tile policy asks
    // that heavy use go elsewhere, which a Gram Panchayat demo is not.
    //
    // If the flatter, lighter basemap is wanted back, Esri's World Light Gray
    // Base is key-free and closest to what CARTO's light_all looked like — but
    // at village zoom it draws almost no labels, which is worse for an officer
    // trying to find a ward.
    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    });

    // A basemap that silently stops loading is exactly the failure that hid the
    // watermark for so long: the markers still plot, the legend still counts,
    // and only a person looking at the screen can tell the map is wrong. Count
    // the failures and say so. A handful of misses at the edge of a pan is
    // normal, so this waits for a real pattern before complaining.
    let tileFailures = 0;
    tiles.on('tileerror', () => {
      tileFailures += 1;
      if (tileFailures === 6) setTilesBroken(true);
    });
    tiles.on('tileload', () => {
      tileFailures = 0;
      setTilesBroken(false);
    });
    tiles.addTo(map);

    groupRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    setMapReady(true);

    return () => {
      map.remove();
      mapRef.current = null;
      groupRef.current = null;
      viewAppliedRef.current = false;
      setMapReady(false);
      setTilesBroken(false);
    };
  }, [canShowMap]);

  // Opening view: the village's own coordinates when the API has them,
  // otherwise the extent of the records themselves.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || viewAppliedRef.current) return;

    if (centre) {
      map.setView(centre, 15);
      viewAppliedRef.current = true;
    } else if (allPoints.length) {
      map.fitBounds(L.latLngBounds(allPoints), { padding: [40, 40], maxZoom: 16 });
      viewAppliedRef.current = true;
    }
  }, [mapReady, centre, allPoints]);

  // Plot the enabled layers.
  useEffect(() => {
    const group = groupRef.current;
    if (!mapReady || !group) return;
    group.clearLayers();

    const layerName = (key: LayerKey) => {
      const style = LAYERS[key];
      return style.i18nKey ? t(style.i18nKey) : isEnglish ? style.labelEn : style.labelMr;
    };

    for (const f of plottable.facilitiesOk) {
      const key = facilityLayer(f.facilityType);
      if (!enabled[key]) continue;
      const style = LAYERS[key];
      const rows: { label: string; value: string }[] = [];
      if (f.ward !== null) {
        rows.push({
          label: isEnglish ? 'Ward' : 'वॉर्ड',
          value: String(f.ward),
        });
      }
      rows.push({
        label: isEnglish ? 'Type' : 'प्रकार',
        value: layerName(key),
      });
      L.marker([f.latitude, f.longitude], { icon: iconFor(key) })
        .bindPopup(
          popupHtml(
            style,
            layerName(key),
            pick(f.name, f.nameMr, isEnglish),
            rows,
            (isEnglish ? f.details : f.detailsMr || f.details) ?? undefined,
          ),
        )
        .addTo(group);
    }

    if (enabled.project) {
      const style = LAYERS.project;
      for (const p of plottable.projectsOk) {
        L.marker([p.latitude, p.longitude], { icon: iconFor('project') })
          .bindPopup(
            popupHtml(
              style,
              isEnglish ? 'Project' : 'प्रकल्प',
              pick(p.name, p.nameMr, isEnglish),
              [
                {
                  label: isEnglish ? 'Status' : 'स्थिती',
                  value: isEnglish ? p.status : p.statusMr || p.status,
                },
                { label: isEnglish ? 'Progress' : 'प्रगती', value: `${p.progress}%` },
                {
                  label: isEnglish ? 'Sanctioned' : 'मंजूर',
                  value: lakhs(p.budget, isEnglish),
                },
                { label: isEnglish ? 'Spent' : 'खर्च', value: lakhs(p.utilized, isEnglish) },
                { label: isEnglish ? 'Ward' : 'वॉर्ड', value: String(p.ward) },
              ],
              pick(p.location, p.locationMr, isEnglish),
            ),
          )
          .addTo(group);
      }
    }

    if (enabled.grievance) {
      const style = LAYERS.grievance;
      for (const g of plottable.grievancesOk) {
        L.marker([g.latitude as number, g.longitude as number], { icon: iconFor('grievance') })
          .bindPopup(
            popupHtml(
              style,
              isEnglish ? 'Grievance' : 'तक्रार',
              pick(g.title, g.titleMr, isEnglish),
              [
                {
                  label: isEnglish ? 'Priority' : 'प्राधान्य',
                  value: isEnglish ? g.priority : g.priorityMr || g.priority,
                },
                {
                  label: isEnglish ? 'Status' : 'स्थिती',
                  value: isEnglish ? g.status : g.statusMr || g.status,
                },
                {
                  label: isEnglish ? 'Department' : 'विभाग',
                  value: pick(g.department, g.departmentMr, isEnglish),
                },
                { label: isEnglish ? 'Ward' : 'वॉर्ड', value: String(g.ward) },
                {
                  label: isEnglish ? 'Filed' : 'दाखल',
                  value: formatDate(g.submittedDate, isEnglish),
                },
              ],
              pick(g.description, g.descriptionMr, isEnglish),
            ),
          )
          .addTo(group);
      }
    }
  }, [mapReady, plottable, enabled, isEnglish, t]);

  const layerLabel = (key: LayerKey) => {
    const style = LAYERS[key];
    return style.i18nKey ? t(style.i18nKey) : isEnglish ? style.labelEn : style.labelMr;
  };

  const visibleLayers = LAYER_ORDER.filter(
    // "Other" is an escape hatch for facility types this screen does not know
    // about; there is no point offering the toggle when nothing lands in it.
    (key) => key !== 'other' || layerCounts.other > 0,
  );

  const unmappedNotes: string[] = [];
  if (unmapped.grievances > 0) {
    unmappedNotes.push(
      isEnglish
        ? `${unmapped.grievances} complaint(s) have no recorded location and are not shown.`
        : `${unmapped.grievances} तक्रारींचे ठिकाण नोंदवलेले नाही, त्या नकाशावर दिसत नाहीत.`,
    );
  }
  if (unmapped.projects > 0) {
    unmappedNotes.push(
      isEnglish
        ? `${unmapped.projects} project(s) have no coordinates and are not shown.`
        : `${unmapped.projects} प्रकल्पांचे निर्देशांक नाहीत, ते नकाशावर दिसत नाहीत.`,
    );
  }
  if (unmapped.facilities > 0) {
    unmappedNotes.push(
      isEnglish
        ? `${unmapped.facilities} facility record(s) have no coordinates and are not shown.`
        : `${unmapped.facilities} सुविधांचे निर्देशांक नाहीत, त्या नकाशावर दिसत नाहीत.`,
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-govblue-900 tracking-tight m-0">
          {t('gis_page.title')}
        </h1>
        <p className="text-xs text-slate-500 mt-1 m-0">
          {isEnglish
            ? 'Facilities, sanctioned works and located complaints, each drawn at its own recorded coordinates.'
            : 'सुविधा, मंजूर कामे आणि ठिकाण नोंद असलेल्या तक्रारी, प्रत्येक तिच्या नोंदवलेल्या निर्देशांकांवर.'}
        </p>
      </div>

      {dataError && <ErrorNotice message={dataError} onRetry={retryAll} />}
      {village.error && <ErrorNotice message={village.error} onRetry={village.refetch} />}

      {dataLoading && (
        <div className="flex items-center justify-center gap-2 py-16 text-slate-400">
          <Loader2 size={18} className="animate-spin" />
          <span className="text-xs font-bold uppercase tracking-wider">
            {isEnglish ? 'Loading map records' : 'नकाशा नोंदी लोड होत आहेत'}
          </span>
        </div>
      )}

      {!dataLoading && !dataError && !canShowMap && (
        <EmptyState
          title={
            isEnglish
              ? 'Nothing to place on the map yet'
              : 'नकाशावर दाखवण्यासारखे अद्याप काही नाही'
          }
          hint={
            isEnglish
              ? 'No facility, project or complaint in this Gram Panchayat has coordinates recorded, and the village itself has no centre point on file.'
              : 'या ग्रामपंचायतीतील कोणत्याही सुविधा, प्रकल्प किंवा तक्रारीचे निर्देशांक नोंदवलेले नाहीत, आणि गावाचा मध्यबिंदूही नोंदीत नाही.'
          }
        />
      )}

      {canShowMap && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
          {/* Map */}
          <div className="lg:col-span-3 rounded-2xl overflow-hidden border border-slate-200 bg-white shadow-sm relative">
            {tilesBroken && (
              <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[500] max-w-md bg-amber-50 border border-amber-300 text-amber-900 rounded-lg shadow-sm px-3 py-2 flex items-start gap-2">
                <Info size={14} className="mt-0.5 flex-shrink-0" />
                <p className="m-0 text-[11px] leading-normal">
                  {isEnglish
                    ? 'The background map is not loading. The markers below come from the Panchayat records and are still correct — only the base map is missing.'
                    : 'पार्श्वभूमीचा नकाशा लोड होत नाही. खालील खुणा पंचायत नोंदींमधून आल्या आहेत आणि त्या बरोबर आहेत — फक्त आधारभूत नकाशा दिसत नाही.'}
                </p>
              </div>
            )}
            <div ref={containerRef} className="w-full h-[550px] z-10" />
            <div className="absolute bottom-4 right-4 bg-white/95 border border-slate-200 text-[10px] font-mono text-slate-600 px-2.5 py-1 rounded shadow-sm select-none z-[400]">
              {centre
                ? `${village.data ? pick(village.data.name, village.data.nameMr, isEnglish) : ''} · ${centre[0].toFixed(4)}, ${centre[1].toFixed(4)}`
                : isEnglish
                  ? `Fitted to ${allPoints.length} mapped record(s) — no village centre on file`
                  : `${allPoints.length} नोंदींनुसार — गावाचा मध्यबिंदू नोंदीत नाही`}
            </div>
          </div>

          {/* Legend and layer toggles. Each row shows the marker the map draws,
              so the shape is the key as much as the colour is. */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-5">
            <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
              <Layers size={16} className="text-govnavy" />
              <h2 className="text-xs font-bold tracking-widest m-0 uppercase text-slate-500">
                {t('gis_page.legend')}
              </h2>
            </div>

            <div className="space-y-2.5">
              {visibleLayers.map((key) => {
                const on = enabled[key];
                const count = layerCounts[key];
                return (
                  <button
                    key={key}
                    onClick={() => setEnabled({ ...enabled, [key]: !on })}
                    aria-pressed={on}
                    className="w-full flex items-center justify-between gap-2 p-2.5 rounded-lg bg-slate-50 border border-slate-200 hover:bg-slate-100 transition-colors text-left"
                  >
                    <span className="flex items-center gap-2.5 min-w-0">
                      <span
                        aria-hidden="true"
                        className="w-[30px] h-[30px] flex-shrink-0"
                        // Static markup assembled from this file's own layer
                        // table; no record data is interpolated into it.
                        dangerouslySetInnerHTML={{ __html: markerHtml(LAYERS[key]) }}
                      />
                      <span className="min-w-0">
                        <span className="block text-xs font-bold text-slate-700 truncate">
                          {layerLabel(key)}
                        </span>
                        <span className="block text-[10px] text-slate-400 tabular-nums">
                          {isEnglish ? `${count} on map` : `${count} नकाशावर`}
                        </span>
                      </span>
                    </span>
                    {on ? (
                      <CheckSquare size={16} className="text-govnavy flex-shrink-0" />
                    ) : (
                      <Square size={16} className="text-slate-300 flex-shrink-0" />
                    )}
                  </button>
                );
              })}
            </div>

            {/* What is missing from the map, stated rather than hidden. */}
            <div className="p-3 bg-govblue-50 rounded-lg border border-govnavy/15 flex items-start gap-2">
              <Info size={14} className="text-govnavy mt-0.5 flex-shrink-0" />
              <div className="text-[10px] text-slate-600 leading-normal space-y-1">
                <p className="m-0">
                  {isEnglish
                    ? 'Click a marker for the record behind it.'
                    : 'नोंद पाहण्यासाठी खुणेवर क्लिक करा.'}
                </p>
                {unmappedNotes.length > 0 ? (
                  unmappedNotes.map((note) => (
                    <p key={note} className="m-0 font-semibold text-slate-700">
                      {note}
                    </p>
                  ))
                ) : (
                  <p className="m-0">
                    {isEnglish
                      ? 'Every recorded facility, project and complaint has coordinates and is on the map.'
                      : 'नोंदवलेल्या सर्व सुविधा, प्रकल्प व तक्रारींना निर्देशांक असून त्या नकाशावर आहेत.'}
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
