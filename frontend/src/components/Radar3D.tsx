import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CSS2DRenderer, CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
import type { AnalyticsRow, Kind } from "../types";
import { Panel, Empty } from "./ui";

const AXES = ["Volume", "Completion", "Mean risk", "Tempo"];
const SERIES: { kind: Kind; name: string; cssVar: string; y: number }[] = [
  { kind: "ddos", name: "DDoS", cssVar: "--accent", y: 1.5 },
  { kind: "bruteforce", name: "Brute Force", cssVar: "--series-2", y: 0.75 },
  { kind: "ratuba", name: "RAT", cssVar: "--warn", y: 0 },
];

function cssColor(v: string): THREE.Color {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const [r, g, b] = raw.split(/\s+/).map(Number);
  return new THREE.Color(`rgb(${r || 120}, ${g || 120}, ${b || 120})`);
}

export function Radar3D({ analytics }: { analytics: AnalyticsRow[] }) {
  const mountRef = useRef<HTMLDivElement>(null);

  const values = useMemo(() => {
    const per = SERIES.map(({ kind }) => {
      const rows = analytics.filter((r) => r.kind === kind);
      const done = rows.filter((r) => r.state === "RESULT");
      const risks = rows.map((r) => r.risk_score).filter((v): v is number => v != null);
      const durs = done.map((r) => r.duration_s).filter((v): v is number => v != null);
      return {
        runs: rows.length,
        completion: rows.length ? done.length / rows.length : 0,
        risk: risks.length ? risks.reduce((a, b) => a + b, 0) / risks.length : 0,
        dur: durs.length ? durs.reduce((a, b) => a + b, 0) / durs.length : 0,
      };
    });
    const maxRuns = Math.max(1, ...per.map((p) => p.runs));
    const maxDur = Math.max(1, ...per.map((p) => p.dur));
    return per.map((p) => [
      p.runs / maxRuns,
      p.completion,
      p.risk,
      p.dur ? Math.min(1, 1 - p.dur / maxDur + 0.15) : 0,
    ]);
  }, [analytics]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !analytics.length) return;
    const W = mount.clientWidth || 400;
    const H = 360;
    const R = 3;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, W / H, 0.1, 100);
    camera.position.set(4.2, 4.0, 6.2);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(W, H);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    const labelRenderer = new CSS2DRenderer();
    labelRenderer.setSize(W, H);
    labelRenderer.domElement.style.position = "absolute";
    labelRenderer.domElement.style.top = "0";
    labelRenderer.domElement.style.pointerEvents = "none";
    mount.appendChild(labelRenderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enablePan = false;
    controls.minDistance = 4;
    controls.maxDistance = 14;
    controls.maxPolarAngle = Math.PI / 2 + 0.25;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.8;
    controls.target.set(0, 0.75, 0);

    const lineCol = cssColor("--line");
    const axPos = (i: number, r: number, y: number) => {
      const a = -Math.PI / 2 + (i / AXES.length) * Math.PI * 2;
      return new THREE.Vector3(Math.cos(a) * R * r, y, Math.sin(a) * R * r);
    };

    // ground grid: concentric rings + spokes
    const grid = new THREE.Group();
    [0.25, 0.5, 0.75, 1].forEach((r) => {
      const pts: THREE.Vector3[] = [];
      for (let s = 0; s <= 48; s++) {
        const a = (s / 48) * Math.PI * 2;
        pts.push(new THREE.Vector3(Math.cos(a) * R * r, 0, Math.sin(a) * R * r));
      }
      grid.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: lineCol, transparent: true, opacity: 0.5 })));
    });
    AXES.forEach((_, i) => {
      const g = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), axPos(i, 1, 0)]);
      grid.add(new THREE.Line(g, new THREE.LineBasicMaterial({ color: lineCol, transparent: true, opacity: 0.5 })));
      const div = document.createElement("div");
      div.textContent = AXES[i];
      div.style.cssText = "font:600 11px system-ui;color:rgb(var(--muted));white-space:nowrap";
      const label = new CSS2DObject(div);
      label.position.copy(axPos(i, 1.2, 0.1));
      grid.add(label);
    });
    scene.add(grid);

    // scenario layers
    values.forEach((vals, si) => {
      const col = cssColor(SERIES[si].cssVar);
      const y = SERIES[si].y;
      const verts = vals.map((v, i) => axPos(i, Math.max(0.03, v), y));
      // filled face (fan from center)
      const pos: number[] = [];
      for (let i = 0; i < verts.length; i++) {
        const a = verts[i], b = verts[(i + 1) % verts.length];
        pos.push(0, y, 0, a.x, a.y, a.z, b.x, b.y, b.z);
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
      geo.computeVertexNormals();
      scene.add(new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.22, side: THREE.DoubleSide, depthWrite: false })));
      // edge loop
      scene.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(verts), new THREE.LineBasicMaterial({ color: col })));
      // vertex nodes + drop lines to ground
      verts.forEach((p) => {
        const node = new THREE.Mesh(new THREE.SphereGeometry(0.06, 12, 12), new THREE.MeshBasicMaterial({ color: col }));
        node.position.copy(p);
        scene.add(node);
        const drop = new THREE.Line(
          new THREE.BufferGeometry().setFromPoints([p, new THREE.Vector3(p.x, 0, p.z)]),
          new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0.18 })
        );
        scene.add(drop);
      });
    });

    let raf = 0;
    const loop = () => {
      raf = requestAnimationFrame(loop);
      controls.update();
      renderer.render(scene, camera);
      labelRenderer.render(scene, camera);
    };
    loop();

    const stopAuto = () => (controls.autoRotate = false);
    renderer.domElement.addEventListener("pointerdown", stopAuto);

    const ro = new ResizeObserver(() => {
      const w = mount.clientWidth || W;
      camera.aspect = w / H;
      camera.updateProjectionMatrix();
      renderer.setSize(w, H);
      labelRenderer.setSize(w, H);
    });
    ro.observe(mount);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      renderer.domElement.removeEventListener("pointerdown", stopAuto);
      controls.dispose();
      renderer.dispose();
      scene.traverse((o) => {
        const any = o as unknown as { geometry?: THREE.BufferGeometry; material?: THREE.Material };
        any.geometry?.dispose?.();
        any.material?.dispose?.();
      });
      mount.removeChild(renderer.domElement);
      mount.removeChild(labelRenderer.domElement);
    };
    // rebuild when the data or theme changes
  }, [values, analytics.length]);

  if (!analytics.length)
    return (
      <Panel title="Scenario profile" sub="3D · drag to rotate">
        <Empty>Run sessions to build the scenario profile.</Empty>
      </Panel>
    );

  return (
    <Panel title="Scenario profile" sub="3D · drag to rotate · scroll to zoom">
      <div ref={mountRef} className="relative w-full" style={{ height: 360, cursor: "grab" }} />
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        {SERIES.map((s) => (
          <span key={s.kind} className="flex items-center gap-1.5 text-2xs text-muted">
            <span className="h-2 w-2 rounded-sm" style={{ background: `rgb(var(${s.cssVar}))` }} />
            {s.name}
          </span>
        ))}
      </div>
    </Panel>
  );
}
