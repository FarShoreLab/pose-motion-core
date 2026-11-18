// Offline interpolation needs measured samples on both sides of a gap.
export function repairReplay(records, {maxGapMs = 350} = {}) {
  const output = records.map(record => structuredClone(record));
  for (let joint = 0; joint < 33; joint++) {
    for (let index = 0; index < output.length; index++) {
      if (records[index].states[joint] === 'measured') continue;
      let left = index - 1, right = index + 1;
      while (left >= 0 && records[left].states[joint] !== 'measured') left--;
      while (right < records.length && records[right].states[joint] !== 'measured') right++;
      if (left < 0 || right >= records.length) continue;
      const before = records[left], after = records[right], current = records[index];
      const sameContext = [before, after].every(record => record.epoch === current.epoch && record.clip === current.clip);
      const gap = after.source_pts_ms - before.source_pts_ms;
      if (!sameContext || gap <= 0 || gap > maxGapMs || current.source_pts_ms <= before.source_pts_ms
          || current.source_pts_ms >= after.source_pts_ms) continue;
      if (records.slice(left, right + 1).some(record => record.epoch !== current.epoch || record.clip !== current.clip)) continue;
      const fraction = (current.source_pts_ms - before.source_pts_ms) / gap;
      for (const field of ['world', 'landmarks']) {
        output[index][field][joint] = {
          x: before[field][joint].x * (1 - fraction) + after[field][joint].x * fraction,
          y: before[field][joint].y * (1 - fraction) + after[field][joint].y * fraction,
          z: before[field][joint].z * (1 - fraction) + after[field][joint].z * fraction
        };
      }
      output[index].states[joint] = 'repaired';
      (output[index].repairs ??= []).push({joint, left_frame_id: before.frame_id, right_frame_id: after.frame_id, bracket_ms: gap});
    }
  }
  return output;
}
