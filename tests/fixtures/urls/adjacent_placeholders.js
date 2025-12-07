// Test adjacent template expressions without separators
// These should consolidate to single FUZZ, not FUZZFUZZ

const url1 = `${prefix}/spaces/${key}${suffix ? `/${suffix}` : ""}`;
const url2 = `${a}/${b}/${c}/${d}/${e}${f}`;
const url3 = `${base}/${middle}${end}`;
