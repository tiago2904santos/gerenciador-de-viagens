export function pad(v) {
  return v < 10 ? '0' + v : String(v);
}

export function hhmm(min) {
  min = parseInt(min || 0, 10) || 0;
  if (!min) return '-';
  return pad(Math.floor(min / 60)) + ':' + pad(min % 60);
}
