#target illustrator

function test() {
    var logFile = new File("D:/atomasi microstock/debug_test.log");
    
    try {
        logFile.open("w");
        logFile.writeln("[START] Debug test script running...");
        
        var svgFile = new File("D:/MicroStock/ADOBESTOCK/stock new/vector-studio-1790965179039.svg");
        logFile.writeln("Opening: " + svgFile.fsName + " (exists=" + svgFile.exists + ")");
        
        if (!svgFile.exists) {
            logFile.writeln("File does not exist!");
            logFile.close();
            return;
        }
        
        var doc = app.open(svgFile);
        logFile.writeln("Opened document successfully.");
        logFile.writeln("doc.layers.length: " + doc.layers.length);
        
        for (var l = 0; l < doc.layers.length; l++) {
            var lyr = doc.layers[l];
            logFile.writeln("Layer " + l + ": '" + lyr.name + "', pageItems=" + lyr.pageItems.length);
            for (var p = 0; p < Math.min(lyr.pageItems.length, 15); p++) {
                var it = lyr.pageItems[p];
                var fillStr = "none";
                var strokeStr = "none";
                try {
                    if (it.filled && it.fillColor) {
                        if (it.fillColor.typename === "RGBColor") {
                            fillStr = "RGB(" + Math.round(it.fillColor.red) + "," + Math.round(it.fillColor.green) + "," + Math.round(it.fillColor.blue) + ")";
                        } else {
                            fillStr = it.fillColor.typename;
                        }
                    }
                } catch(e) { fillStr = "err:" + e.message; }
                logFile.writeln("   Item " + p + ": type=" + it.typename + ", filled=" + it.filled + " (" + fillStr + "), items=" + (it.pageItems ? it.pageItems.length : 0));
                if (it.pageItems && it.pageItems.length > 0) {
                    var ch = it.pageItems[0];
                    var chFill = "none";
                    try {
                        if (ch.filled && ch.fillColor) {
                            if (ch.fillColor.typename === "RGBColor") {
                                chFill = "RGB(" + Math.round(ch.fillColor.red) + "," + Math.round(ch.fillColor.green) + "," + Math.round(ch.fillColor.blue) + ")";
                            } else {
                                chFill = ch.fillColor.typename;
                            }
                        }
                    } catch(e) { chFill = "err:" + e.message; }
                    logFile.writeln("      Child 0: type=" + ch.typename + ", filled=" + ch.filled + " (" + chFill + ")");
                }
            }
        }
        
        doc.close(SaveOptions.DONOTSAVECHANGES);
        logFile.writeln("[DONE]");
        logFile.close();
    } catch(e) {
        try {
            logFile.writeln("[ERROR] " + e.message + " line=" + e.line);
            logFile.close();
        } catch(ex) {}
    }
}

test();
