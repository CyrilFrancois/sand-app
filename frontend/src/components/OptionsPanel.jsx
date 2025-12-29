import { useState } from "react";

export default function OptionsPanel({ disabled, onGenerate }) {
  const [variants, setVariants] = useState(4);
  const [wallHeight, setWallHeight] = useState(3);
  const [wallThickness, setWallThickness] = useState("");
  const [basePlate, setBasePlate] = useState(false);

  return (
    <div style={{ marginBottom: 24 }}>
      <div>
        Variants:
        <input
          type="number"
          min="1"
          max="4"
          value={variants}
          onChange={e => setVariants(e.target.value)}
        />
      </div>

      <div>
        Wall height (mm):
        <input
          type="number"
          value={wallHeight}
          onChange={e => setWallHeight(e.target.value)}
        />
      </div>

      <div>
        Wall thickness (optional):
        <input
          type="number"
          value={wallThickness}
          onChange={e => setWallThickness(e.target.value)}
        />
      </div>

      <div>
        <label>
          <input
            type="checkbox"
            checked={basePlate}
            onChange={e => setBasePlate(e.target.checked)}
          />
          Base plate
        </label>
      </div>

      <button
        disabled={disabled}
        onClick={() =>
          onGenerate({
            variants,
            wallHeight,
            wallThickness,
            basePlate
          })
        }
      >
        Generate
      </button>
    </div>
  );
}