export async function generate(payload) {
  const form = new FormData();
  form.append("image", payload.image);
  form.append("variants", payload.variants);
  form.append("wall_height", payload.wallHeight);
  if (payload.wallThickness) form.append("wall_thickness", payload.wallThickness);
  form.append("base_plate", payload.basePlate);

  const res = await fetch(
    `${import.meta.env.VITE_BACKEND_URL}/generate`,
    { method: "POST", body: form }
  );

  return res.blob();
}