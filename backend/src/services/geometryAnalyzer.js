/**
 * Geometry Analyzer Service
 * Analyzes DXF geometry to detect holes, perimeter, and other properties.
 */

function analyzeGeometry(dxf) {
  const entities = getAllEntities(dxf);
  const layers = extractLayers(dxf);
  const boundingBox = computeBoundingBox(entities);
  const titleBlock = detectTitleBlock(entities, boundingBox);
  const holes = detectHoles(entities, titleBlock, boundingBox);
  const perimeter = calculateOuterPerimeter(entities, titleBlock, boundingBox);
  const entityCount = entities.length;
  const units = dxf.header && dxf.header.$INSUNITS
    ? getUnitName(dxf.header.$INSUNITS)
    : 'Unknown';

  return { holes, perimeter, layers, entityCount, boundingBox, units };
}

// Flatten all entities from all blocks and model space
function getAllEntities(dxf) {
  const entities = [];

  if (dxf.entities) {
    entities.push(...dxf.entities);
  }

  // Also include block entities if needed
  if (dxf.blocks) {
    for (const blockName of Object.keys(dxf.blocks)) {
      const block = dxf.blocks[blockName];
      if (block && block.entities) {
        // Only include non-system blocks
        if (!blockName.startsWith('*')) {
          entities.push(...block.entities);
        }
      }
    }
  }

  return entities;
}

// Extract unique layer names
function extractLayers(dxf) {
  const layerSet = new Set();

  if (dxf.tables && dxf.tables.layer && dxf.tables.layer.layers) {
    for (const layerName of Object.keys(dxf.tables.layer.layers)) {
      layerSet.add(layerName);
    }
  }

  const entities = getAllEntities(dxf);
  entities.forEach(e => {
    if (e.layer) layerSet.add(e.layer);
  });

  return Array.from(layerSet);
}

// Compute overall bounding box of all geometry
function computeBoundingBox(entities) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

  for (const entity of entities) {
    const pts = getEntityPoints(entity);
    for (const pt of pts) {
      if (pt.x < minX) minX = pt.x;
      if (pt.y < minY) minY = pt.y;
      if (pt.x > maxX) maxX = pt.x;
      if (pt.y > maxY) maxY = pt.y;
    }
  }

  if (!isFinite(minX)) return { minX: 0, minY: 0, maxX: 0, maxY: 0, width: 0, height: 0 };

  return { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY };
}

// Get representative points from an entity for bounding box
function getEntityPoints(entity) {
  const pts = [];

  switch (entity.type) {
    case 'LINE':
      if (entity.vertices) {
        entity.vertices.forEach(v => pts.push(v));
      } else {
        if (entity.start) pts.push(entity.start);
        if (entity.end) pts.push(entity.end);
      }
      break;

    case 'CIRCLE':
      if (entity.center) {
        const r = entity.radius || 0;
        pts.push({ x: entity.center.x - r, y: entity.center.y });
        pts.push({ x: entity.center.x + r, y: entity.center.y });
        pts.push({ x: entity.center.x, y: entity.center.y - r });
        pts.push({ x: entity.center.x, y: entity.center.y + r });
      }
      break;

    case 'ARC':
      if (entity.center) {
        const r = entity.radius || 0;
        pts.push({ x: entity.center.x - r, y: entity.center.y - r });
        pts.push({ x: entity.center.x + r, y: entity.center.y + r });
      }
      break;

    case 'LWPOLYLINE':
    case 'POLYLINE':
      const verts = entity.vertices || [];
      verts.forEach(v => pts.push(v));
      break;

    case 'SPLINE':
      const ctrlPts = entity.controlPoints || entity.fitPoints || [];
      ctrlPts.forEach(v => pts.push(v));
      break;

    case 'ELLIPSE':
      if (entity.center) {
        const mx = entity.majorAxisEndPoint
          ? Math.sqrt(entity.majorAxisEndPoint.x ** 2 + entity.majorAxisEndPoint.y ** 2)
          : 0;
        pts.push({ x: entity.center.x - mx, y: entity.center.y - mx });
        pts.push({ x: entity.center.x + mx, y: entity.center.y + mx });
      }
      break;

    default:
      break;
  }

  return pts;
}

// Detect the title block: the largest axis-aligned rectangle
// that is likely a title block (common in sheet drawings)
function detectTitleBlock(entities, boundingBox) {
  const rects = [];

  for (const entity of entities) {
    const rect = tryExtractRectangle(entity);
    if (rect) rects.push(rect);
  }

  if (rects.length === 0) return null;

  // Title block is typically close to the drawing's bounding box
  // Find the largest rectangle that spans most of the drawing
  let bestRect = null;
  let bestArea = 0;

  for (const rect of rects) {
    const area = rect.width * rect.height;
    if (area > bestArea) {
      bestArea = area;
      bestRect = rect;
    }
  }

  // Only treat as title block if it's very large (>70% of bounding box area)
  if (bestRect && boundingBox.width > 0 && boundingBox.height > 0) {
    const bbArea = boundingBox.width * boundingBox.height;
    if (bestArea / bbArea > 0.5) {
      return bestRect;
    }
  }

  return null;
}

// Try to extract a rectangle from a closed polyline or 4-line entity
function tryExtractRectangle(entity) {
  if (entity.type === 'LWPOLYLINE' || entity.type === 'POLYLINE') {
    const verts = entity.vertices || [];
    if (verts.length === 4 || (verts.length === 5 && isClosingVertex(verts[0], verts[4]))) {
      const v = verts.slice(0, 4);
      return getRectFromVertices(v);
    }
    // Also handle rectangles with closing vertex
    if (verts.length === 5) {
      const v = verts.slice(0, 4);
      return getRectFromVertices(v);
    }
  }
  return null;
}

function isClosingVertex(v1, v2) {
  if (!v1 || !v2) return false;
  return Math.abs(v1.x - v2.x) < 0.001 && Math.abs(v1.y - v2.y) < 0.001;
}

function getRectFromVertices(verts) {
  if (verts.length < 4) return null;

  const xs = verts.map(v => v.x);
  const ys = verts.map(v => v.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);

  // Check if it's actually axis-aligned
  const isAxisAligned = verts.every(
    v => (Math.abs(v.x - minX) < 0.01 || Math.abs(v.x - maxX) < 0.01) &&
         (Math.abs(v.y - minY) < 0.01 || Math.abs(v.y - maxY) < 0.01)
  );

  if (!isAxisAligned) return null;

  const width = maxX - minX;
  const height = maxY - minY;

  if (width < 1 || height < 1) return null;

  return { minX, minY, maxX, maxY, width, height };
}

// Check if a point is inside the title block
function isInsideTitleBlock(point, titleBlock, margin = 1) {
  if (!titleBlock) return false;
  return (
    point.x >= titleBlock.minX - margin &&
    point.x <= titleBlock.maxX + margin &&
    point.y >= titleBlock.minY - margin &&
    point.y <= titleBlock.maxY + margin
  );
}

// Detect holes: circles, closed polylines that are NOT the outer boundary or title block
function detectHoles(entities, titleBlock, boundingBox) {
  let holeCount = 0;
  const bbArea = boundingBox.width * boundingBox.height;

  for (const entity of entities) {
    if (isHole(entity, titleBlock, boundingBox, bbArea)) {
      holeCount++;
    }
  }

  return holeCount;
}

function isHole(entity, titleBlock, boundingBox, bbArea) {
  // Circles are always holes (except very large ones spanning most of drawing)
  if (entity.type === 'CIRCLE') {
    if (!entity.center || !entity.radius) return false;
    const r = entity.radius;
    const circleArea = Math.PI * r * r;
    // If circle is tiny relative to bounding box, count it
    if (bbArea > 0 && circleArea / bbArea > 0.5) return false; // outer circle
    // Check if inside title block
    if (isInsideTitleBlock(entity.center, titleBlock)) return false;
    return true;
  }

  // Closed polylines — detect as holes
  if (entity.type === 'LWPOLYLINE' || entity.type === 'POLYLINE') {
    const verts = entity.vertices || [];
    if (verts.length < 3) return false;

    // Check if polyline is closed
    const isClosed = entity.closed ||
      (verts.length >= 2 && isClosingVertex(verts[0], verts[verts.length - 1]));
    if (!isClosed) return false;

    // Get bounding box of this polyline
    const xs = verts.map(v => v.x);
    const ys = verts.map(v => v.y);
    const pMinX = Math.min(...xs);
    const pMaxX = Math.max(...xs);
    const pMinY = Math.min(...ys);
    const pMaxY = Math.max(...ys);
    const pArea = (pMaxX - pMinX) * (pMaxY - pMinY);
    const center = { x: (pMinX + pMaxX) / 2, y: (pMinY + pMaxY) / 2 };

    // Exclude outer boundary (largest closed shape)
    if (bbArea > 0 && pArea / bbArea > 0.8) return false;

    // Exclude title block
    if (isInsideTitleBlock(center, titleBlock)) return false;

    // Must be a meaningful hole (not a tiny artifact)
    if (pArea < 0.01) return false;

    return true;
  }

  // Ellipses can be holes
  if (entity.type === 'ELLIPSE') {
    if (!entity.center) return false;
    if (isInsideTitleBlock(entity.center, titleBlock)) return false;
    return true;
  }

  return false;
}

// Calculate outer perimeter by finding the largest closed boundary
function calculateOuterPerimeter(entities, titleBlock, boundingBox) {
  let maxArea = 0;
  let outerPerimeter = 0;

  for (const entity of entities) {
    const result = getPerimeterIfOuter(entity, titleBlock, boundingBox);
    if (result && result.area > maxArea) {
      maxArea = result.area;
      outerPerimeter = result.perimeter;
    }
  }

  // If no closed boundary found, estimate from bounding box minus title block
  if (outerPerimeter === 0 && boundingBox.width > 0) {
    outerPerimeter = 2 * (boundingBox.width + boundingBox.height);
  }

  return Math.round(outerPerimeter * 100) / 100;
}

function getPerimeterIfOuter(entity, titleBlock, boundingBox) {
  const bbArea = boundingBox.width * boundingBox.height;

  if (entity.type === 'LWPOLYLINE' || entity.type === 'POLYLINE') {
    const verts = entity.vertices || [];
    if (verts.length < 3) return null;

    const isClosed = entity.closed ||
      (verts.length >= 2 && isClosingVertex(verts[0], verts[verts.length - 1]));
    if (!isClosed) return null;

    const xs = verts.map(v => v.x);
    const ys = verts.map(v => v.y);
    const pMinX = Math.min(...xs);
    const pMaxX = Math.max(...xs);
    const pMinY = Math.min(...ys);
    const pMaxY = Math.max(...ys);
    const area = (pMaxX - pMinX) * (pMaxY - pMinY);
    const center = { x: (pMinX + pMaxX) / 2, y: (pMinY + pMaxY) / 2 };

    // Must be substantial (>20% of bounding box)
    if (bbArea > 0 && area / bbArea < 0.1) return null;

    // Exclude title block
    if (isInsideTitleBlock(center, titleBlock)) return null;

    // Calculate actual perimeter
    let perimeter = 0;
    const closedVerts = [...verts];
    if (!isClosingVertex(verts[0], verts[verts.length - 1])) {
      closedVerts.push(verts[0]);
    }

    for (let i = 0; i < closedVerts.length - 1; i++) {
      const dx = closedVerts[i + 1].x - closedVerts[i].x;
      const dy = closedVerts[i + 1].y - closedVerts[i].y;
      perimeter += Math.sqrt(dx * dx + dy * dy);
    }

    return { area, perimeter };
  }

  if (entity.type === 'CIRCLE') {
    const r = entity.radius || 0;
    const area = Math.PI * r * r;
    if (bbArea > 0 && area / bbArea < 0.1) return null;
    if (isInsideTitleBlock(entity.center, titleBlock)) return null;
    return { area, perimeter: 2 * Math.PI * r };
  }

  return null;
}

function getUnitName(code) {
  const units = {
    0: 'Unitless', 1: 'Inches', 2: 'Feet', 3: 'Miles',
    4: 'Millimeters', 5: 'Centimeters', 6: 'Meters', 7: 'Kilometers',
    8: 'Microinches', 9: 'Mils', 10: 'Yards', 11: 'Angstroms',
    12: 'Nanometers', 13: 'Microns', 14: 'Decimeters', 15: 'Decameters',
    16: 'Hectometers', 17: 'Gigameters', 18: 'Astronomical Units',
    19: 'Light Years', 20: 'Parsecs'
  };
  return units[code] || 'Unknown';
}

module.exports = { analyzeGeometry };
