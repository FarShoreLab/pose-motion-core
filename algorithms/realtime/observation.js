// Both trackers consume the same raw frame. Validity refers to each policy's key joints.
// Rendering, timing, bitmap ownership and audit persistence belong to the caller.
export function observeFrame(record, tracker, referenceTracker, missing = []) {
  const filtered = tracker.observe(record, {missing});
  const reference = referenceTracker.observe(record, {missing});
  return {
    filtered_observation: filtered,
    filtered_valid: filtered.valid,
    v4_filtered_observation: reference,
    v4_filtered_valid: reference.valid
  };
}
