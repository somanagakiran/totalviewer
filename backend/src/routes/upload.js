const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const DxfParser = require('dxf-parser');
const { analyzeGeometry } = require('../services/geometryAnalyzer');

const router = express.Router();

// Configure multer storage
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    const uploadDir = path.join(__dirname, '../../uploads');
    if (!fs.existsSync(uploadDir)) {
      fs.mkdirSync(uploadDir, { recursive: true });
    }
    cb(null, uploadDir);
  },
  filename: (req, file, cb) => {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1e9);
    cb(null, uniqueSuffix + '-' + file.originalname);
  }
});

// File filter — only allow DXF files
const fileFilter = (req, file, cb) => {
  const ext = path.extname(file.originalname).toLowerCase();
  if (ext === '.dxf') {
    cb(null, true);
  } else {
    cb(new Error('Only .DXF files are allowed'), false);
  }
};

const upload = multer({
  storage,
  fileFilter,
  limits: { fileSize: 50 * 1024 * 1024 } // 50MB limit
});

// POST /api/upload
router.post('/upload', upload.single('dxfFile'), async (req, res) => {
  if (!req.file) {
    return res.status(400).json({ error: 'No file uploaded or invalid file type.' });
  }

  const filePath = req.file.path;
  const fileName = req.file.originalname;

  try {
    const fileContent = fs.readFileSync(filePath, 'utf-8');
    const parser = new DxfParser();
    const dxf = parser.parseSync(fileContent);

    if (!dxf) {
      return res.status(400).json({ error: 'Failed to parse DXF file. File may be corrupted or unsupported.' });
    }

    const analysis = analyzeGeometry(dxf);

    return res.json({
      fileName,
      holes: analysis.holes,
      perimeter: analysis.perimeter,
      layers: analysis.layers,
      entityCount: analysis.entityCount,
      boundingBox: analysis.boundingBox,
      units: analysis.units
    });
  } catch (err) {
    console.error('DXF Processing Error:', err.message);
    return res.status(500).json({ error: 'Failed to process DXF file: ' + err.message });
  }
});

// Error handler for multer
router.use((err, req, res, next) => {
  if (err instanceof multer.MulterError) {
    return res.status(400).json({ error: err.message });
  }
  if (err) {
    return res.status(400).json({ error: err.message });
  }
  next();
});

module.exports = router;
