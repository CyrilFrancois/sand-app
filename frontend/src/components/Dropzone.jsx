export default function Dropzone({ onSelect }) {
  return (
    <div style={{ border: "2px dashed gray", padding: 24, marginBottom: 24 }}>
      <input
        type="file"
        accept="image/*"
        onChange={e => onSelect(e.target.files[0])}
      />
    </div>
  );
}