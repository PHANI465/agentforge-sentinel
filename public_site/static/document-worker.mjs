import {Unzip, UnzipInflate, unzipSync} from './vendor/fflate.mjs';
import {analyzeDocuments} from './document-checks.mjs';

function officeParts(data, format) {
  let size = 0;
  let entries = 0;
  const lengths = new Map();
  // Read the directory first, then stream each selected entry. The directory can
  // understate a DEFLATE stream's expanded length, so it is only a preflight bound.
  unzipSync(data, {filter(file) {
    if (++entries > 400) throw new Error();
    const relevant = format === 'docx' ? file.name === 'word/document.xml'
      : /^xl\/(?:workbook\.xml|_rels\/workbook\.xml\.rels|sharedStrings\.xml|worksheets\/[a-z0-9._-]+\.xml)$/i.test(file.name);
    if (!relevant) return false;
    size += file.originalSize;
    if (size > 12_000_000 || lengths.has(file.name) ||
        (file.compression === 0 && file.size !== file.originalSize)) throw new Error();
    lengths.set(file.name, file.originalSize);
    return false;
  }});
  const parts = Object.create(null);
  const started = new Set();
  let expanded = 0;
  const archive = new Unzip(file => {
    const declared = lengths.get(file.name);
    if (declared === undefined) return;
    if (started.has(file.name)) throw new Error();
    started.add(file.name);
    const output = new Uint8Array(declared);
    let written = 0;
    file.ondata = (error, chunk, final) => {
      if (error) throw error;
      expanded += chunk.length;
      if (expanded > 12_000_000 || written + chunk.length > declared) throw new Error();
      output.set(chunk, written);
      written += chunk.length;
      if (final) {
        if (written !== declared) throw new Error();
        parts[file.name] = output;
      }
    };
    file.start();
  });
  archive.register(UnzipInflate);
  for (let offset = 0; offset < data.length; offset += 4096) {
    const end = Math.min(offset + 4096, data.length);
    archive.push(data.subarray(offset, end), end === data.length);
  }
  for (const [name, length] of lengths) {
    if (parts[name]?.byteLength !== length) throw new Error();
  }
  return parts;
}

self.onmessage = ({data}) => {
  try {
    if (data.type === 'office') {
      const value = officeParts(data.data, data.format);
      self.postMessage({ok: true, value}, Object.values(value).map(part => part.buffer));
    } else if (data.type === 'analyze') {
      self.postMessage({ok: true, value: analyzeDocuments(data.documents, data.options)});
    } else {
      self.postMessage({ok: false});
    }
  } catch {
    self.postMessage({ok: false});
  }
};
