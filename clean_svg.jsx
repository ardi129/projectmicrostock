// ==============================================================================
// ADOBE ILLUSTRATOR EXTENDSCRIPT (.jsx) - CLEAN & CONVERT TO EPS 10 + JPEG
// Versi 4 - Spesifikasi Standar Microstock
// ==============================================================================
// 1. Unhide & Unlock semua objek
// 2. Hapus elemen tersembunyi, stray points, empty paths
// 3. Deteksi & Hapus background bawaan SVG (pembacaan warna 4 sudut 90 derajat kanvas)
// 4. Ukuran Artboard: 5200 × 2925 px, Artwork di-center proporsional
// 5. Color Mode: RGB & Document Raster Effects: High (300 ppi)
// 6. Restrukturisasi 3 LAYER UTAMA:
//    - "Art Line" (Paling Atas): HANYA outline / ink hitam pekat konsisten
//    - "Color" (Tengah): Semua fill warna subjek dengan z-order asli
//    - "Background" (Paling Bawah): Rectangle cream soft vintage 5200 × 2925 px
// 7. Kebersihan Artboard: Area luar artboard dibersihkan/ter-crop rapi
// 8. Simpan ke EPS 10 (RGB) & JPEG (300 ppi, Artboard-clipped)
// ==============================================================================

#target illustrator

function main() {
    var userInteraction = app.userInteractionLevel;
    app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;

    var projectFolder = null;
    try {
        if ($.fileName) {
            projectFolder = (new File($.fileName)).parent;
        }
    } catch(e) {}
    if (!projectFolder || !projectFolder.exists) {
        projectFolder = new Folder("d:/atomasi microstock");
    }

    var configFile = new File(projectFolder + "/clean_config.json");
    var logFile = new File(projectFolder + "/clean_status.log");

    function logMsg(msg) {
        try {
            logFile.open("a");
            logFile.writeln(msg);
            logFile.close();
        } catch(e) {}
    }

    try {
        logFile.open("w");
        logFile.write("");
        logFile.close();
    } catch(e) {}

    try {
        logMsg("[INIT] Skrip ExtendScript v4 (Artboard 5200×2925 px, RGB, 300 ppi, EPS 10) dimulai...");

        if (!configFile.exists) {
            logMsg("[ERROR] File konfigurasi clean_config.json tidak ditemukan: " + configFile.fsName);
            return;
        }

        configFile.open("r");
        var configContent = configFile.read();
        configFile.close();

        var config = null;
        try {
            config = eval('(' + configContent + ')');
        } catch(e) {
            logMsg("[ERROR] Gagal membaca JSON konfigurasi: " + e.message);
            return;
        }

        var inputFolderPath = config.input_folder;
        var outputFolderPath = config.output_folder;

        var inputFolder = new Folder(inputFolderPath);
        var outputFolder = new Folder(outputFolderPath);

        if (!inputFolder.exists) {
            logMsg("[ERROR] Folder input tidak ditemukan: " + inputFolderPath);
            return;
        }

        if (!outputFolder.exists) {
            outputFolder.create();
        }

        var svgFiles = inputFolder.getFiles("*.svg");
        if (svgFiles.length === 0) {
            logMsg("[INFO] Tidak ditemukan file .svg di folder input.");
            return;
        }

        // --------------------------------------------------------------------------
        // LOGIKA CEK FILE: Ambil semua nama file di folder output (tanpa ekstensi)
        // --------------------------------------------------------------------------
        var existingBaseNames = {};
        var existingCount = 0;
        var outputFiles = outputFolder.getFiles();

        if (outputFiles && outputFiles.length > 0) {
            for (var o = 0; o < outputFiles.length; o++) {
                var oFile = outputFiles[o];
                if (oFile instanceof File) {
                    var oName = oFile.name;
                    var oBase = oName.replace(/\.[^\.]+$/, "").toLowerCase();
                    if (oBase) {
                        existingBaseNames[oBase] = true;
                        existingCount++;
                    }
                }
            }
            logMsg("[CHECK] Memeriksa folder output: " + outputFolder.fsName + " (" + existingCount + " file sudah ada).");
        }

        // Filter file SVG: Skip jika nama dasarnya sudah ada di folder output (misal sudah ada .eps, .jpg, dll.)
        var filesToProcess = [];
        var skippedCount = 0;

        for (var s = 0; s < svgFiles.length; s++) {
            var sFile = svgFiles[s];
            var sBase = sFile.name.replace(/\.[^\.]+$/, "").toLowerCase();
            if (existingBaseNames[sBase]) {
                logMsg("  -> [SKIP] " + sFile.name + " (sudah ada di folder output sebagai \"" + sBase + ".*\")");
                skippedCount++;
            } else {
                filesToProcess.push(sFile);
            }
        }

        if (skippedCount > 0) {
            logMsg("[INFO] Total file di-skip: " + skippedCount + " file (sudah ada di output).");
        }

        if (filesToProcess.length === 0) {
            logMsg("==================================================");
            logMsg(" Semua file SVG (" + svgFiles.length + ") sudah ada di folder output.");
            logMsg(" Tidak ada file baru yang perlu diproses. Selesai! 🎉");
            logMsg("[COMPLETE] Pembersihan & Konversi Selesai!");
            logMsg("==================================================");
            return;
        }

        logMsg("[INFO] Total File Input : " + svgFiles.length + " file SVG");
        logMsg("[INFO] File Di-skip     : " + skippedCount + " file (sudah ada di output)");
        logMsg("[INFO] File Diproses    : " + filesToProcess.length + " file");

        try {
            app.preferences.setBooleanPreference("scaleStrokes", true);
        } catch(e) {}
    } catch(initErr) {
        logMsg("[ERROR INIT] " + initErr.message);
        return;
    }

    for (var f = 0; f < filesToProcess.length; f++) {
        var fileObj = filesToProcess[f];
        logMsg("[PROCESSING " + (f + 1) + "/" + filesToProcess.length + "] " + fileObj.name);

        var doc = null;
        try {
            doc = app.open(fileObj);

            // STEP 1: Unhide & Unlock Semua Elemen
            unlockAndUnhideAll(doc);

            // STEP 2: Hapus Elemen Tersembunyi, Stray Points & Empty Paths
            var removedHidden = removeHiddenItems(doc);
            var removedStrayEmpty = cleanStrayAndEmptyPaths(doc);
            logMsg("   -> Cleaned: " + removedHidden + " hidden items, " + removedStrayEmpty + " stray/empty paths.");

            // STEP 3: Deteksi & Hapus Background Bawaan SVG
            // (path/rect dengan 4 sudut ~90 derajat yang menutupi >= 90% artwork)
            var removedOldBg = removeOldSvgBackground(doc);
            logMsg("   -> Background lama SVG dibuang: " + removedOldBg + " elemen.");

            // STEP 4: Setup Artboard 5200 × 2925 px, RGB, 300 ppi & Scale Artwork Proporsional
            setupArtboardAndScale5200x2925(doc);
            logMsg("   -> Artboard di-set: 5200 × 2925 px (RGB, 300 ppi), Artwork di-scale proporsional di tengah.");

            // STEP 5: Restrukturisasi 3 Layer Utama (Art Line, Color, Background)
            organizeInto3Layers(doc);
            logMsg("   -> Layer terstruktur: [Art Line] subjek utama, [Color] warna subjek, [Background] #C9D3CC 5200x2925.");

            // STEP 6: Kebersihan Artboard - Bersihkan semua objek di luar batas artboard 5200 × 2925 px
            cleanOutsideArtboard(doc);
            logMsg("   -> Kebersihan Artboard: Area luar artboard dibersihkan/ter-crop rapi.");

            // STEP 7: Simpan File ke Folder Output (EPS 10 RGB & JPEG)
            var baseName = fileObj.name.replace(/\.[^\.]+$/, "");

            var epsFile = new File(outputFolder.fsName + "/" + baseName + ".eps");
            saveAsEPS10(doc, epsFile);

            var jpgFile = new File(outputFolder.fsName + "/" + baseName + ".jpg");
            exportAsJPEG(doc, jpgFile);

            logMsg("   -> [SUCCESS] Tersimpan (.eps, .jpg): " + baseName);

        } catch(err) {
            logMsg("   -> [ERROR] Gagal memproses " + fileObj.name + ": " + err.message);
        } finally {
            if (doc !== null) {
                try {
                    doc.close(SaveOptions.DONOTSAVECHANGES);
                } catch(e) {}
            }
        }
    }

    app.userInteractionLevel = userInteraction;
    logMsg("[COMPLETE] Pembersihan & Konversi Selesai!");
}

// ==============================================================================
// HELPER FUNCTIONS
// ==============================================================================

function unlockAndUnhideAll(doc) {
    for (var i = 0; i < doc.layers.length; i++) {
        var layer = doc.layers[i];
        layer.locked = false;
        layer.visible = true;
    }
    for (var j = 0; j < doc.pageItems.length; j++) {
        var item = doc.pageItems[j];
        try {
            item.locked = false;
            item.hidden = false;
        } catch(e) {}
    }
}

function removeHiddenItems(doc) {
    var count = 0;
    for (var i = doc.pageItems.length - 1; i >= 0; i--) {
        var item = doc.pageItems[i];
        if (item.hidden) {
            try {
                item.remove();
                count++;
            } catch(e) {}
        }
    }
    return count;
}

function cleanStrayAndEmptyPaths(doc) {
    var count = 0;
    for (var i = doc.pathItems.length - 1; i >= 0; i--) {
        var pathItem = doc.pathItems[i];
        try {
            if (pathItem.pathPoints.length <= 1) {
                pathItem.remove();
                count++;
                continue;
            }
            if (!pathItem.filled && !pathItem.stroked) {
                pathItem.remove();
                count++;
                continue;
            }
        } catch(e) {}
    }
    return count;
}

function getArtworkBounds(doc) {
    var minX = Infinity, maxY = -Infinity, maxX = -Infinity, minY = Infinity;
    var count = 0;
    for (var i = 0; i < doc.pageItems.length; i++) {
        var item = doc.pageItems[i];
        if (item.hidden) continue;
        try {
            var b = item.geometricBounds; // [left, top, right, bottom]
            if (b[0] < minX) minX = b[0];
            if (b[1] > maxY) maxY = b[1];
            if (b[2] > maxX) maxX = b[2];
            if (b[3] < minY) minY = b[3];
            count++;
        } catch(e) {}
    }
    if (count === 0) {
        return doc.artboards[0].artboardRect;
    }
    return [minX, maxY, maxX, minY];
}

function getItemColor(item) {
    try {
        if (item.typename === "PathItem") {
            if (item.filled && item.fillColor) return item.fillColor;
            if (item.stroked && item.strokeColor) return item.strokeColor;
        } else if (item.typename === "CompoundPathItem") {
            if (item.pathItems.length > 0) {
                var sub = item.pathItems[0];
                if (sub.filled && sub.fillColor) return sub.fillColor;
                if (sub.stroked && sub.strokeColor) return sub.strokeColor;
            }
        }
    } catch(e) {}
    return null;
}

function isLightBackgroundColor(colorObj) {
    if (!colorObj) return false;
    try {
        if (colorObj.typename === "RGBColor") {
            var r = colorObj.red;
            var g = colorObj.green;
            var b = colorObj.blue;
            var br = (r * 0.299 + g * 0.587 + b * 0.114);
            // Warna terang vintage: cream, beige, white, light gray (brightness >= 140)
            return (br >= 140 && r >= 140 && g >= 130 && b >= 110);
        } else if (colorObj.typename === "GrayColor") {
            return colorObj.gray <= 35;
        } else if (colorObj.typename === "CMYKColor") {
            return colorObj.black <= 20 && (colorObj.cyan + colorObj.magenta) <= 45;
        }
    } catch(e) {}
    return false;
}

/**
 * Bandingkan apakah dua warna sama atau sangat mirip
 */
function isColorVerySimilar(c1, c2, tolerance) {
    if (!c1 || !c2) return false;
    if (!tolerance) tolerance = 28;
    try {
        if (c1.typename === "RGBColor" && c2.typename === "RGBColor") {
            var diff = Math.abs(c1.red - c2.red) +
                       Math.abs(c1.green - c2.green) +
                       Math.abs(c1.blue - c2.blue);
            return diff <= (tolerance * 3);
        } else if (c1.typename === "CMYKColor" && c2.typename === "CMYKColor") {
            var diffCMYK = Math.abs(c1.cyan - c2.cyan) +
                           Math.abs(c1.magenta - c2.magenta) +
                           Math.abs(c1.yellow - c2.yellow) +
                           Math.abs(c1.black - c2.black);
            return diffCMYK <= (tolerance * 2);
        } else if (c1.typename === "GrayColor" && c2.typename === "GrayColor") {
            return Math.abs(c1.gray - c2.gray) <= tolerance;
        }
    } catch(e) {}
    return false;
}

/**
 * Cek apakah warna ini cocok dengan salah satu warna background yang harus dibuang
 */
function matchesAnyBackgroundColor(itemColor, bgList, tolerance) {
    if (!itemColor || !bgList || bgList.length === 0) return false;
    for (var i = 0; i < bgList.length; i++) {
        if (isColorVerySimilar(itemColor, bgList[i], tolerance)) {
            return true;
        }
    }
    return false;
}

/**
 * Hapus SEMUA shape di seluruh dokumen yang memiliki warna yang sama / sangat mirip
 * dengan daftar warna background lama, baik di luar kanvas maupun di dalam celah desain/huruf
 */
function removeAllShapesMatchingBackgroundColors(container, bgList, tolerance) {
    var count = 0;
    if (!container || !bgList || bgList.length === 0) return 0;

    for (var i = container.pageItems.length - 1; i >= 0; i--) {
        var it = container.pageItems[i];
        try {
            if (it.typename === "PathItem" || it.typename === "CompoundPathItem") {
                var col = getItemColor(it);
                // JANGAN hapus warna outline/artline hitam
                if (col && !isPureOutlineColor(col)) {
                    if (matchesAnyBackgroundColor(col, bgList, tolerance)) {
                        it.remove();
                        count++;
                    }
                }
            } else if (it.typename === "GroupItem") {
                count += removeAllShapesMatchingBackgroundColors(it, bgList, tolerance);
                if (it.pageItems.length === 0) {
                    try { it.remove(); } catch(e) {}
                }
            }
        } catch(e) {}
    }
    return count;
}

/**
 * Deteksi & Hapus Background Bawaan SVG Secara Maksimal:
 * 1. Deteksi semua shape kanvas background (4 sudut 90 derajat yang menutupi kanvas >= 70% artboard)
 * 2. AMBIL SEMUA WARNA dari shape kanvas background tersebut (warna biru, hijau, cyan yang sengaja dibuat kontras)
 * 3. Hapus SEMUA shape dengan warna tersebut (dan yang sangat mirip) di seluruh dokumen (baik di luar maupun di dalam celah desain/teks)!
 * 4. Hapus juga shape kanvas terluar jika masih ada.
 */
function removeOldSvgBackground(doc) {
    if (doc.pageItems.length === 0) return 0;

    var bounds = getArtworkBounds(doc);
    var totalW = Math.abs(bounds[2] - bounds[0]);
    var totalH = Math.abs(bounds[1] - bounds[3]);

    if (totalW <= 0 || totalH <= 0) return 0;

    var removedCount = 0;
    var bgColorsToDelete = [];

    // LANGKAH 1: Cari shape background kanvas (4 sudut 90 derajat, luas >= 70% artboard)
    // dan SIMPAN WARNANYA ke bgColorsToDelete!
    for (var i = 0; i < doc.pageItems.length; i++) {
        var item = doc.pageItems[i];
        try {
            if (isBackgroundRect(item, totalW, totalH)) {
                var col = getItemColor(item);
                if (col && !isPureOutlineColor(col)) {
                    if (!matchesAnyBackgroundColor(col, bgColorsToDelete, 10)) {
                        bgColorsToDelete.push(col);
                    }
                }
            }
        } catch(e) {}
    }

    // Jika belum terdeteksi dari isBackgroundRect, periksa shape terbesar di dokumen (w >= 70% && h >= 70%)
    if (bgColorsToDelete.length === 0) {
        for (var bIdx = 0; bIdx < doc.pageItems.length; bIdx++) {
            var bItem = doc.pageItems[bIdx];
            try {
                var bW = Math.abs(bItem.width);
                var bH = Math.abs(bItem.height);
                if ((bW / totalW >= 0.70) && (bH / totalH >= 0.70)) {
                    var bCol = getItemColor(bItem);
                    if (bCol && !isPureOutlineColor(bCol)) {
                        if (!matchesAnyBackgroundColor(bCol, bgColorsToDelete, 10)) {
                            bgColorsToDelete.push(bCol);
                        }
                    }
                }
            } catch(e) {}
        }
    }

    // LANGKAH 2: Hapus SEMUA shape yang memiliki warna background lama (dan warna yang sangat mirip)
    // di seluruh dokumen: baik di luar kanvas, di belakang subjek, di dalam celah ombak, di dalam lubang huruf/teks.
    if (bgColorsToDelete.length > 0) {
        var shapesDeleted = removeAllShapesMatchingBackgroundColors(doc, bgColorsToDelete, 28);
        removedCount += shapesDeleted;
    }

    // LANGKAH 3: Hapus sisa kanvas luar / bounding rect jika masih ada
    for (var k = doc.pageItems.length - 1; k >= 0; k--) {
        var rItem = doc.pageItems[k];
        try {
            if (isBackgroundRect(rItem, totalW, totalH)) {
                rItem.remove();
                removedCount++;
            }
        } catch(e) {}
    }

    return removedCount;
}

/**
 * Cek apakah item adalah kanvas background atau bounding rectangle SVG
 * (Memiliki 4 sudut 90 derajat atau menutupi >= 70% luas artboard)
 */
function isBackgroundRect(item, totalW, totalH) {
    if (item.typename !== "PathItem" && item.typename !== "CompoundPathItem") return false;

    var itemW = Math.abs(item.width);
    var itemH = Math.abs(item.height);

    var wRatio = itemW / totalW;
    var hRatio = itemH / totalH;

    // Menutupi >= 70% dimensi artwork
    if (wRatio < 0.70 || hRatio < 0.70) return false;

    if (item.typename === "PathItem") {
        if (isRectangularPath(item)) return true;
        if (wRatio >= 0.85 && hRatio >= 0.85) return true;
    } else if (item.typename === "CompoundPathItem") {
        if (item.pathItems.length === 1 && isRectangularPath(item.pathItems[0])) {
            return true;
        }
        if (wRatio >= 0.80 && hRatio >= 0.80) return true;
    }
    return false;
}

function isRectangularPath(pathItem) {
    try {
        var pts = pathItem.pathPoints;
        if (pts.length === 4) {
            var coords = [];
            for (var i = 0; i < 4; i++) {
                coords.push({ x: pts[i].anchor[0], y: pts[i].anchor[1] });
            }
            var xs = [coords[0].x, coords[1].x, coords[2].x, coords[3].x];
            var ys = [coords[0].y, coords[1].y, coords[2].y, coords[3].y];
            xs.sort(function(a, b) { return a - b; });
            ys.sort(function(a, b) { return a - b; });

            var xSpan = Math.abs(xs[3] - xs[0]);
            var ySpan = Math.abs(ys[3] - ys[0]);
            var xGap = Math.abs(xs[1] - xs[0]) + Math.abs(xs[3] - xs[2]);
            var yGap = Math.abs(ys[1] - ys[0]) + Math.abs(ys[3] - ys[2]);

            return (xGap <= xSpan * 0.08 && yGap <= ySpan * 0.08);
        }
    } catch(e) {}
    return false;
}

// ==============================================================================
// STEP 4: Setup Artboard 5200 × 2925 px & Scale Artwork Proporsional di Tengah
// ==============================================================================
function setupArtboardAndScale5200x2925(doc) {
    if (doc.pageItems.length === 0) return;

    // Pastikan Color Mode = RGB
    try {
        app.executeMenuCommand('doc-color-rgb');
    } catch(e) {}

    // Raster Effects Settings: High (300 ppi)
    try {
        doc.rasterEffectSettings.resolution = 300;
        doc.rasterEffectSettings.colorModel = RasterColorModel.COLORMODELRGB;
    } catch(e) {}

    // Set Ukuran Artboard Tepat 5200 × 2925 px: [left=0, top=0, right=5200, bottom=-2925]
    doc.artboards[0].artboardRect = [0, 0, 5200, -2925];

    var bounds = getArtworkBounds(doc);
    var artW = Math.abs(bounds[2] - bounds[0]);
    var artH = Math.abs(bounds[1] - bounds[3]);

    if (artW <= 0 || artH <= 0) return;

    // Target dimensi di dalam artboard 5200 × 2925 px dengan safe margin proporsional (5050 × 2775)
    var targetW = 5050.0;
    var targetH = 2775.0;

    var scaleRatio = Math.min(targetW / artW, targetH / artH);
    var scalePercent = scaleRatio * 100.0;

    // Snapshot top-level items saja per layer sebelum dipindahkan
    var targetLayer = doc.layers[0];
    var itemsToGroup = [];
    for (var l = 0; l < doc.layers.length; l++) {
        var lyr = doc.layers[l];
        lyr.locked  = false;
        lyr.visible = true;
        for (var i = 0; i < lyr.pageItems.length; i++) {
            if (lyr.pageItems[i].parent === lyr) {
                itemsToGroup.push(lyr.pageItems[i]);
            }
        }
    }

    if (itemsToGroup.length === 0) return;

    // Buat tempGroup di targetLayer, pindahkan top-level items ke dalamnya
    var tempGroup = targetLayer.groupItems.add();
    for (var k = 0; k < itemsToGroup.length; k++) {
        try {
            if (itemsToGroup[k] !== tempGroup) {
                itemsToGroup[k].move(tempGroup, ElementPlacement.PLACEATEND);
            }
        } catch(e) {}
    }

    // Scale seragam
    tempGroup.resize(
        scalePercent, scalePercent,
        true, true, true, true, scalePercent,
        Transformation.CENTER
    );

    // Posisikan artwork tepat di tengah-tengah (center) artboard 5200 × 2925 px
    // Center X = 2600, Center Y = -1462.5
    var gBounds = tempGroup.geometricBounds;
    var gW = Math.abs(gBounds[2] - gBounds[0]);
    var gH = Math.abs(gBounds[1] - gBounds[3]);

    tempGroup.left = 2600.0 - (gW / 2.0);
    tempGroup.top  = -1462.5 + (gH / 2.0);

    // Snapshot direct children tempGroup (parent === tempGroup) untuk dipindahkan kembali
    var directChildren = [];
    for (var j = tempGroup.pageItems.length - 1; j >= 0; j--) {
        var child = tempGroup.pageItems[j];
        if (child.parent === tempGroup) {
            directChildren.push(child);
        }
    }
    for (var m = 0; m < directChildren.length; m++) {
        try {
            directChildren[m].move(targetLayer, ElementPlacement.PLACEATBEGINNING);
        } catch(e) {}
    }

    try { tempGroup.remove(); } catch(e) {}
}

/**
 * Buat Background #C9D3CC tepat mengikuti artboard 5200 × 2925 px
 */
function createSoftCreamBackground(doc, bgLayer) {
    // Koordinat artboard 5200 × 2925 px: top=0, left=0, width=5200, height=2925
    var bgRect = bgLayer.pathItems.rectangle(0, 0, 5200, 2925);

    var bgColor = new RGBColor();
    bgColor.red   = 201;
    bgColor.green = 211;
    bgColor.blue  = 204; // Hex #C9D3CC (C9=201, D3=211, CC=204)

    bgRect.filled = true;
    bgRect.fillColor = bgColor;
    bgRect.stroked = false;
    bgRect.name = "Background #C9D3CC (5200x2925)";
}

/**
 * Kebersihan Artboard: Pastikan tidak ada objek, garis (stroke), atau path yang tercecer di luar artboard.
 * Bersihkan seluruh elemen liar di luar bounds [0, 0, 5200, -2925].
 */
function cleanOutsideArtboard(doc) {
    var bgLayer = null;
    try { bgLayer = doc.layers.getByName("Background"); } catch(e) {}

    // Hapus item yang berada sepenuhnya di luar artboard (kecuali background)
    for (var i = doc.pageItems.length - 1; i >= 0; i--) {
        var it = doc.pageItems[i];
        if (bgLayer && (it.parent === bgLayer || it.layer === bgLayer)) continue;
        try {
            var b = it.geometricBounds; // [left, top, right, bottom]
            if (b[2] <= 0 || b[0] >= 5200 || b[1] <= -2925 || b[3] >= 0) {
                it.remove();
            }
        } catch(e) {}
    }

    // Bersihkan kembali stray points / empty paths
    cleanStrayAndEmptyPaths(doc);
}

// ==============================================================================
// DETEKSI ART LINE - HANYA SUBJEK UTAMA (OBJEK BESAR & KONSISTEN)
// ==============================================================================

/**
 * Cek apakah warna adalah warna outline/line art murni (hitam pekat atau dark ink)
 */
function isPureOutlineColor(colorObj) {
    if (!colorObj) return false;
    try {
        if (colorObj.typename === "RGBColor") {
            var r = colorObj.red;
            var g = colorObj.green;
            var b = colorObj.blue;
            var brightness = (r * 0.299 + g * 0.587 + b * 0.114);
            // Hitam / Dark ink outline: r, g, b <= 75 dan brightness <= 65
            if (r <= 75 && g <= 75 && b <= 75 && brightness <= 65) return true;
        } else if (colorObj.typename === "CMYKColor") {
            // K >= 60% atau total CMYK sangat gelap
            if (colorObj.black >= 60) return true;
            if ((colorObj.cyan + colorObj.magenta + colorObj.yellow + colorObj.black) >= 220 && colorObj.black >= 45) return true;
        } else if (colorObj.typename === "GrayColor") {
            return colorObj.gray >= 60;
        } else if (colorObj.typename === "SpotColor") {
            return isPureOutlineColor(colorObj.spot.color);
        }
    } catch(e) {}
    return false;
}

/**
 * Cek apakah sebuah item memiliki warna dark ink / outline
 * (Mendukung baik STROKE maupun FILL karena Vectorizer AI menghasilkan filled paths)
 */
function isItemDarkArtLine(item) {
    if (!item) return false;
    try {
        if (item.typename === "PathItem") {
            if (item.stroked && isPureOutlineColor(item.strokeColor)) return true;
            if (item.filled && isPureOutlineColor(item.fillColor)) return true;
            return false;
        } else if (item.typename === "CompoundPathItem") {
            if (item.pathItems.length > 0) {
                var first = item.pathItems[0];
                if (first.stroked && isPureOutlineColor(first.strokeColor)) return true;
                if (first.filled && isPureOutlineColor(first.fillColor)) return true;
            }
            return false;
        } else if (item.typename === "GroupItem") {
            return getArtLineScore(item).isArtLine;
        }
    } catch(e) {}
    return false;
}

/**
 * Hitung skor "line art consistency" sebuah item
 * Return: { isArtLine: bool, score: 0-1 }
 */
function getArtLineScore(item) {
    var darkCount = 0;
    var totalCount = 0;

    function scan(it) {
        try {
            if (it.typename === "PathItem") {
                totalCount++;
                if ((it.stroked && isPureOutlineColor(it.strokeColor)) ||
                    (it.filled && isPureOutlineColor(it.fillColor))) {
                    darkCount++;
                }
            } else if (it.typename === "CompoundPathItem") {
                totalCount++;
                if (it.pathItems.length > 0) {
                    var p0 = it.pathItems[0];
                    if ((p0.stroked && isPureOutlineColor(p0.strokeColor)) ||
                        (p0.filled && isPureOutlineColor(p0.fillColor))) {
                        darkCount++;
                    }
                }
            } else if (it.typename === "GroupItem") {
                for (var i = 0; i < it.pageItems.length; i++) {
                    scan(it.pageItems[i]);
                }
            }
        } catch(e) {}
    }

    scan(item);

    if (totalCount === 0) return { isArtLine: false, score: 0 };
    var score = darkCount / totalCount;
    return { isArtLine: score >= 0.50, score: score };
}

/**
 * Cek apakah item adalah Art Line SUBJEK UTAMA:
 * 1. Berwarna hitam / dark ink (fill atau stroke)
 * 2. Mengabaikan bintik noise yang sangat kecil (< 2px)
 */
function isMainSubjectArtLine(item, artW, artH) {
    if (!item) return false;
    try {
        if (!isItemDarkArtLine(item)) return false;

        var iW = Math.abs(item.width);
        var iH = Math.abs(item.height);

        // Hanya abaikan noise bintik sangat kecil (lebar < 2px dan tinggi < 2px)
        if (iW < 2.0 && iH < 2.0) return false;

        return true;
    } catch(e) {}
    return false;
}

/**
 * Perkuat art line: normalkan warna hitam pekat murni agar konsisten
 */
function makeLineArtStrong(item) {
    try {
        var pureBlack = new RGBColor();
        pureBlack.red   = 0;
        pureBlack.green = 0;
        pureBlack.blue  = 0;

        if (item.typename === "PathItem") {
            if (item.stroked && isPureOutlineColor(item.strokeColor)) {
                item.strokeColor = pureBlack;
                if (item.strokeWidth < 1.0) item.strokeWidth = 1.0;
            }
            if (item.filled && isPureOutlineColor(item.fillColor)) {
                item.fillColor = pureBlack;
            }
        } else if (item.typename === "CompoundPathItem") {
            for (var i = 0; i < item.pathItems.length; i++) {
                makeLineArtStrong(item.pathItems[i]);
            }
        } else if (item.typename === "GroupItem") {
            for (var j = 0; j < item.pageItems.length; j++) {
                makeLineArtStrong(item.pageItems[j]);
            }
        }
    } catch(e) {}
}

function getItemColorInfo(item) {
    try {
        if (item.typename === "CompoundPathItem") {
            if (item.pathItems.length > 0) {
                return getItemColorInfo(item.pathItems[0]);
            }
        }
        if (item.typename === "PathItem") {
            if (item.filled && item.fillColor) {
                return formatColorString(item.fillColor);
            }
        }
        if (item.typename === "GroupItem") {
            for (var i = 0; i < item.pageItems.length; i++) {
                var info = getItemColorInfo(item.pageItems[i]);
                if (info.key !== "NONE" && info.key !== "DEFAULT") return info;
            }
        }
    } catch(e) {}
    return { key: "DEFAULT", name: "Color_Default" };
}

function formatColorString(colorObj) {
    try {
        if (colorObj.typename === "RGBColor") {
            var r = Math.round(colorObj.red);
            var g = Math.round(colorObj.green);
            var b = Math.round(colorObj.blue);
            // Quantize ke nearest-16 untuk grouping warna yang lebih rapi
            var rq = Math.round(r / 16) * 16;
            var gq = Math.round(g / 16) * 16;
            var bq = Math.round(b / 16) * 16;
            return {
                key: "RGB_" + rq + "_" + gq + "_" + bq,
                name: "Color (RGB " + r + "-" + g + "-" + b + ")"
            };
        } else if (colorObj.typename === "CMYKColor") {
            var c = Math.round(colorObj.cyan);
            var m = Math.round(colorObj.magenta);
            var y = Math.round(colorObj.yellow);
            var k = Math.round(colorObj.black);
            // Quantize ke nearest-10 untuk grouping
            var cq = Math.round(c / 10) * 10;
            var mq = Math.round(m / 10) * 10;
            var yq = Math.round(y / 10) * 10;
            var kq = Math.round(k / 10) * 10;
            return {
                key: "CMYK_" + cq + "_" + mq + "_" + yq + "_" + kq,
                name: "Color (CMYK " + c + "-" + m + "-" + y + "-" + k + ")"
            };
        } else if (colorObj.typename === "GrayColor") {
            var gv = Math.round(colorObj.gray);
            var gqv = Math.round(gv / 10) * 10;
            return {
                key: "GRAY_" + gqv,
                name: "Color (Gray " + gv + "%)"
            };
        } else if (colorObj.typename === "SpotColor") {
            return {
                key: "SPOT_" + colorObj.spot.name,
                name: "Color (" + colorObj.spot.name + ")"
            };
        } else if (colorObj.typename === "NoColor") {
            return { key: "NONE", name: "No_Fill" };
        }
    } catch(e) {}
    return { key: "DEFAULT", name: "Color_Default" };
}

// ==============================================================================
// RESTRUKTURISASI 3 LAYER UTAMA & GROUP PER WARNA
// ==============================================================================
function organizeInto3Layers(doc) {
    var artLineLayer = getOrCreateLayer(doc, "Art Line");
    var colorLayer   = getOrCreateLayer(doc, "Color");
    var bgLayer      = getOrCreateLayer(doc, "Background");

    // Susun urutan layer: Art Line (atas) > Color (tengah) > Background (bawah)
    artLineLayer.move(doc, ElementPlacement.PLACEATBEGINNING);
    colorLayer.move(artLineLayer, ElementPlacement.PLACEAFTER);
    bgLayer.move(colorLayer, ElementPlacement.PLACEAFTER);

    // Buat Background Cream Soft (full artboard, paling bawah)
    createSoftCreamBackground(doc, bgLayer);

    var abRect = doc.artboards[0].artboardRect;
    var artW = Math.abs(abRect[2] - abRect[0]);
    var artH = Math.abs(abRect[1] - abRect[3]);

    // ==================================================================
    // KUMPULKAN semua item dalam urutan z-order asli (TOP ke BOTTOM)
    //
    // Di Illustrator ExtendScript:
    //   doc.layers[0]      = layer paling ATAS
    //   doc.layers[last]   = layer paling BAWAH
    //   layer.pageItems[0] = item paling ATAS dalam layer
    //
    // Snapshot SEBELUM ada pergerakan agar referensi tetap valid.
    // ==================================================================
    var allItems = []; // [0] = top-most, [last] = bottom-most

    for (var l = 0; l < doc.layers.length; l++) { // top layer first
        var layer = doc.layers[l];
        if (layer === artLineLayer || layer === colorLayer || layer === bgLayer) continue;

        var snap = [];
        for (var p = 0; p < layer.pageItems.length; p++) {
            if (layer.pageItems[p].parent === layer) {
                snap.push(layer.pageItems[p]);
            }
        }
        for (var s = 0; s < snap.length; s++) {
            allItems.push(snap[s]); // snap[0] = top of this layer
        }
    }

    // ==================================================================
    // PINDAHKAN items ke target layer dengan z-order terjaga
    //
    // Teknik: iterasi dari BAWAH ke ATAS (allItems[last] dulu),
    // setiap item di-PLACEATBEGINNING (taruh di paling atas layer).
    //
    // Hasil: item bottom-most dipindah duluan → duduk di bawah,
    //        lalu item atas menimpa ke atas satu per satu.
    //        Z-order akhir = sama persis dengan aslinya. ✓
    //
    // TIDAK ADA color grouping — grouping per warna merusak z-order!
    // Contoh: shape putih "lubang huruf" dan shape berwarna di bawahnya
    // harus berdekatan di z-order; jika dipisah ke group berbeda,
    // teks jadi hilang atau blob warna muncul di tempat salah.
    // ==================================================================
    for (var j = allItems.length - 1; j >= 0; j--) { // bottom to top
        var curItem = allItems[j];
        if (!curItem || !curItem.typename) continue;

        try {
            // Art Line: path/group yang punya STROKE hitam & cukup besar
            if (isMainSubjectArtLine(curItem, artW, artH)) {
                makeLineArtStrong(curItem);
                curItem.move(artLineLayer, ElementPlacement.PLACEATBEGINNING);
            } else {
                // Semua lainnya: masuk Color layer langsung, z-order terjaga
                curItem.move(colorLayer, ElementPlacement.PLACEATBEGINNING);
            }
        } catch(e) {}
    }

    // Hapus layer lama yang sudah kosong
    for (var k = doc.layers.length - 1; k >= 0; k--) {
        var lyr = doc.layers[k];
        if (lyr.name !== "Art Line" && lyr.name !== "Color" && lyr.name !== "Background") {
            try {
                if (lyr.pageItems.length === 0) lyr.remove();
            } catch(e) {}
        }
    }
}

function getOrCreateLayer(doc, layerName) {
    try {
        return doc.layers.getByName(layerName);
    } catch(e) {
        var newLayer = doc.layers.add();
        newLayer.name = layerName;
        return newLayer;
    }
}

function saveAsEPS10(doc, destFile) {
    var epsSaveOptions = new EPSSaveOptions();
    epsSaveOptions.compatibility = Compatibility.ILLUSTRATOR10;
    epsSaveOptions.embedAllFonts = true;
    epsSaveOptions.embedLinkedFiles = true;
    epsSaveOptions.includeDocumentThumbnails = true;
    epsSaveOptions.saveMultipleArtboards = false;
    epsSaveOptions.cmykPostScript = false; // RGB Color Mode
    epsSaveOptions.postScript = EPSPostScriptLevelEnum.LEVEL2;

    doc.saveAs(destFile, epsSaveOptions);
}

function exportAsJPEG(doc, destFile) {
    var exportOptions = new ExportOptionsJPEG();
    exportOptions.antiAliasing     = true;
    exportOptions.qualitySetting   = 100;
    exportOptions.artboardClipping = true;
    exportOptions.optimization     = true;
    // Scale 100% - artboard sudah 5000px lebar, JPEG langsung dari ukuran artboard
    exportOptions.horizontalScale  = 100;
    exportOptions.verticalScale    = 100;

    doc.exportFile(destFile, ExportType.JPEG, exportOptions);
}

main();




