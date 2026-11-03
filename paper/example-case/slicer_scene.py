"""Example-case figure, Slicer side: the CT and its 12 DICOM SEGs as unsmoothed 3D surfaces, side by side.

Runs inside 3D Slicer. make_figure.py calls one function per request through the Slicer MCP
server, so the UI and the server stay responsive between the slow steps:

    ns = runpy.run_path(THIS_FILE)
    ns["loadCT"](ctDir)
    ns["loadSeg"](model, segDir)   # once per model in ORDER
    ns["addCoronalCT"]()
    ns["arrange"]()                # or arrange(rows=[[...], [...]])
    ns["capture"](rawPng)          # returns where each model sits in the image, for annotate.py;
                                   # with rows, once per row: capture(rawPng, models=row, sizeFrom=rows)

Every function returns a JSON string. Nodes it creates are found again by the TAG attribute,
so each step can be re-run on its own.
"""

import json
import os
import resource
import subprocess
import time

import ctk
import numpy as np
import qt
import slicer
import vtk
from vtk.util import numpy_support
from DICOMLib import DICOMUtils

ORDER = [
    "total", "lung_vessels",
    "clin_ct_body", "clin_ct_body_composition", "clin_ct_cardiac", "clin_ct_digestive",
    "clin_ct_lungs", "clin_ct_muscles", "clin_ct_organs", "clin_ct_peripheral_bones",
    "clin_ct_ribs", "clin_ct_vertebrae",
]
TAG = "ExampleCaseFigure.Model"


def _memory():
    rssKB = int(subprocess.run(["ps", "-o", "rss=", "-p", str(os.getpid())],
                               capture_output=True, text=True).stdout.strip())
    # ru_maxrss is in bytes on macOS
    return {
        "slicerRSS_GB": round(rssKB / 1024**2, 2),
        "slicerPeakRSS_GB": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**3, 2),
        "dcmqiPeakRSS_GB": round(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024**3, 2),
    }


def _node(model):
    for className in ("vtkMRMLSegmentationNode", "vtkMRMLModelNode"):
        for node in slicer.util.getNodesByClass(className):
            if node.GetAttribute(TAG) == model:
                return node
    return None


def _defaultOrder():
    return (["CT"] if _node("CT") else []) + ORDER


def _ct(required=True):
    """The CT volume: the one loadCT tagged, else the only untagged scalar volume in the scene."""
    volumes = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
    tagged = [v for v in volumes if v.GetAttribute(TAG) == "CT volume"]
    if tagged:
        return tagged[0]
    untagged = [v for v in volumes if not v.GetAttribute(TAG)]
    if len(untagged) == 1:
        return untagged[0]
    if not untagged and not required:
        return None
    raise RuntimeError(f"expected one CT volume, found {[v.GetName() for v in untagged]}")


def _loadDicomSeries(ctDir):
    # A throwaway database, so the user's own DICOM database is left alone
    with DICOMUtils.TemporaryDICOMDatabase() as db:
        DICOMUtils.importDicom(ctDir, db)
        seriesUIDs = [series for patient in db.patients() for study in db.studiesForPatient(patient)
                      for series in db.seriesForStudy(study)]
        if len(seriesUIDs) != 1:
            raise RuntimeError(f"expected one series in {ctDir}, found {len(seriesUIDs)}")
        nodeIDs = DICOMUtils.loadSeriesByUID(seriesUIDs, enabledPluginClassNames=["DICOMScalarVolumePlugin"])
    volumes = [n for n in map(slicer.mrmlScene.GetNodeByID, nodeIDs) if n and n.IsA("vtkMRMLScalarVolumeNode")]
    if len(volumes) != 1:
        raise RuntimeError(f"expected one volume from {ctDir}, got {nodeIDs}")
    return volumes[0]


def loadCT(ctDir):
    """Load the CT series in ctDir, unless a CT is already in the scene."""
    existing = _ct(required=False)
    if existing:
        return json.dumps({"ct": existing.GetName(), "skipped": "already loaded"})
    t0 = time.time()
    volume = _loadDicomSeries(ctDir)
    volume.SetAttribute(TAG, "CT volume")
    return json.dumps({"ct": volume.GetName(), "dims": volume.GetImageData().GetDimensions(),
                       "load_s": round(time.time() - t0, 1), **_memory()})


def loadSeg(model, segDir, smoothing=0.0):
    """Load <segDir>/<model>_0.dcm through the DICOM SEG plugin and build closed surfaces with the given smoothing."""
    if _node(model):
        return json.dumps({"model": model, "skipped": "already loaded"})
    path = os.path.join(segDir, model + "_0.dcm")
    t0 = time.time()
    # A throwaway database, so the user's own DICOM database is left alone
    with DICOMUtils.TemporaryDICOMDatabase() as db:
        db.insert(path, False, False)  # filePath, storeFile, generateThumbnail
        loadablesByPlugin, _ = DICOMUtils.getLoadablesFromFileLists([[path]], ["DICOMSegmentationPlugin"])
        nodeIDs = DICOMUtils.loadLoadables(loadablesByPlugin)
    segNodes = [slicer.mrmlScene.GetNodeByID(i) for i in nodeIDs]
    segNodes = [n for n in segNodes if n and n.IsA("vtkMRMLSegmentationNode")]
    if len(segNodes) != 1:
        raise RuntimeError(f"{model}: expected one segmentation node, got {nodeIDs}")
    node = segNodes[0]
    node.SetName(model)
    node.SetAttribute(TAG, model)
    return _showSurfaces(model, node, smoothing, time.time() - t0)


def adopt(model, nodeID, smoothing=0.0):
    """Use a segmentation already in the scene for <model> instead of loading it again."""
    node = slicer.mrmlScene.GetNodeByID(nodeID)
    node.SetAttribute(TAG, model)
    return _showSurfaces(model, node, smoothing, 0.0)


def _showSurfaces(model, node, smoothing, tLoad):
    t0 = time.time()
    # The loader may already have made smoothed surfaces; rebuild them with our smoothing factor
    node.GetSegmentation().SetConversionParameter("Smoothing factor", str(smoothing))
    node.RemoveClosedSurfaceRepresentation()
    node.CreateClosedSurfaceRepresentation()
    displayNode = node.GetDisplayNode()
    displayNode.SetVisibility(True)
    displayNode.SetVisibility3D(True)
    displayNode.SetPreferredDisplayRepresentationName3D("Closed surface")

    triangles = 0
    segmentation = node.GetSegmentation()
    for i in range(segmentation.GetNumberOfSegments()):
        polyData = node.GetClosedSurfaceInternalRepresentation(segmentation.GetNthSegmentID(i))
        if polyData:
            triangles += polyData.GetNumberOfCells()
    return json.dumps({
        "model": model,
        "segments": segmentation.GetNumberOfSegments(),
        "triangles_M": round(triangles / 1e6, 2),
        "load_s": round(tLoad, 1),
        "surface_s": round(time.time() - t0, 1),
        **_memory(),
    })


def addCoronalCT(y=-10.0, window=400, level=40, marginMm=10.0):
    """Show one coronal CT slice as a textured plane, at its true position and scale, cropped to the body.

    A model with a texture, rather than a slice view shown in 3D, so its size and resolution do not
    change with the layout. The texture is held by a hidden volume node so that the scene owns it.
    """
    ct = _ct()
    ijkToRas = vtk.vtkMatrix4x4()
    ct.GetIJKToRASMatrix(ijkToRas)
    for column in range(3):
        for row in range(3):
            if row != column and abs(ijkToRas.GetElement(row, column)) > 1e-3:
                raise RuntimeError("CT is not axis-aligned; a fixed j index would not be a coronal plane")
    j = int(round((y - ijkToRas.GetElement(1, 3)) / ijkToRas.GetElement(1, 1)))

    # Crop left-right to the body outline
    voxels = slicer.util.arrayFromVolume(ct)
    xMin, xMax = _localBounds(_node("clin_ct_body"))[0:2]
    iRange = sorted((x - ijkToRas.GetElement(0, 3)) / ijkToRas.GetElement(0, 0)
                    for x in (xMin - marginMm, xMax + marginMm))
    i0, i1 = max(0, int(np.floor(iRange[0]))), min(voxels.shape[2] - 1, int(np.ceil(iRange[1])))
    nK = voxels.shape[0]

    slab = voxels[:, j, i0:i1 + 1].astype(np.float32)
    grey = np.clip((slab - (level - window / 2)) / window * 255, 0, 255).astype(np.uint8)
    image = vtk.vtkImageData()
    image.SetDimensions(grey.shape[1], grey.shape[0], 1)  # texture u along i, v along k
    image.GetPointData().SetScalars(numpy_support.numpy_to_vtk(grey.ravel(), deep=True))
    textureName = "ExampleCaseFigure CT coronal texture"
    textureNode = slicer.mrmlScene.GetFirstNodeByName(textureName) or \
        slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", textureName)
    textureNode.SetHideFromEditors(True)
    textureNode.SetAttribute(TAG, "CT texture")
    textureNode.SetAndObserveImageData(image)

    def ras(i, k):
        return ijkToRas.MultiplyPoint((i, j, k, 1))[0:3]
    plane = vtk.vtkPlaneSource()
    plane.SetOrigin(ras(i0 - 0.5, -0.5))
    plane.SetPoint1(ras(i1 + 0.5, -0.5))
    plane.SetPoint2(ras(i0 - 0.5, nK - 0.5))
    plane.Update()
    modelNode = _node("CT") or slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "CT coronal")
    modelNode.SetAttribute(TAG, "CT")
    modelNode.SetAndObservePolyData(plane.GetOutput())
    if not modelNode.GetDisplayNode():
        modelNode.CreateDefaultDisplayNodes()
    displayNode = modelNode.GetDisplayNode()
    displayNode.SetColor(1, 1, 1)
    displayNode.SetAmbient(1.0)  # flat, unlit: show the grey values as they are
    displayNode.SetDiffuse(0.0)
    displayNode.SetSpecular(0.0)
    displayNode.SetBackfaceCulling(False)
    displayNode.SetScalarVisibility(False)
    displayNode.SetVisibility2D(False)
    displayNode.SetInterpolateTexture(True)
    displayNode.SetTextureImageDataConnection(textureNode.GetImageDataConnection())
    return json.dumps({"ct": ct.GetName(), "j": j, "y_mm": round(ras(i0, 0)[1], 1),
                       "i": [i0, i1], "texture_px": [grey.shape[1], grey.shape[0]]})


def _localBounds(node):
    if node.IsA("vtkMRMLModelNode"):
        return list(node.GetPolyData().GetBounds())
    return _surfaceBounds(node)


def _surfaceBounds(node):
    """Bounds of the closed surfaces in the node's own coordinates (the labelmap grid can be much larger)."""
    box = vtk.vtkBoundingBox()
    segmentation = node.GetSegmentation()
    for i in range(segmentation.GetNumberOfSegments()):
        polyData = node.GetClosedSurfaceInternalRepresentation(segmentation.GetNthSegmentID(i))
        if polyData and polyData.GetNumberOfPoints():
            box.AddBounds(polyData.GetBounds())
    bounds = [0.0] * 6
    box.GetBounds(bounds)
    return bounds


def _localPoints(node, maxPoints=1000000):
    """Surface points in the node's own coordinates, subsampled; enough to find extents to within a few mm."""
    if node.IsA("vtkMRMLModelNode"):
        arrays = [numpy_support.vtk_to_numpy(node.GetPolyData().GetPoints().GetData())]
    else:
        segmentation = node.GetSegmentation()
        arrays = []
        for i in range(segmentation.GetNumberOfSegments()):
            polyData = node.GetClosedSurfaceInternalRepresentation(segmentation.GetNthSegmentID(i))
            if polyData and polyData.GetNumberOfPoints():
                arrays.append(numpy_support.vtk_to_numpy(polyData.GetPoints().GetData()))
    step = max(1, sum(len(a) for a in arrays) // maxPoints)
    return np.concatenate([a[::step] for a in arrays])


def arrange(gapMm=40.0, order=None, azimuth=30.0, elevation=25.0, rotateCT=False, background="slicer", rows=None):
    """Turn every model the same way, then shift each along R-L so they sit side by side, in `order`.

    The rotation is `azimuth` degrees about the S-I axis (patient right towards the viewer), then
    `elevation` degrees tipping the top towards the viewer, about one centre shared by all models so
    that anatomy stays level across them. The camera stays anterior and orthographic, so a model's
    depth never affects the layout. Patient right (+R) is on the viewer's left, so the first model
    gets the largest R offset. The CT plane stays facing the viewer unless `rotateCT`.

    `rows`, a list of lists of models, overrides `order`: each row is centred on x = 0, and each
    row after the first is shifted inferiorly to sit `gapMm` below the one before it.
    """
    rows = rows or [order or _defaultOrder()]
    rows = [[(m, _node(m)) for m in row if _node(m)] for row in rows]
    nodes = [entry for row in rows for entry in row]
    box = vtk.vtkBoundingBox()
    for _, node in nodes:
        if node.IsA("vtkMRMLSegmentationNode"):
            box.AddBounds(_surfaceBounds(node))
    centre = [0.0] * 3
    box.GetCenter(centre)
    rotation = vtk.vtkTransform()
    rotation.PostMultiply()
    rotation.Translate(-centre[0], -centre[1], -centre[2])
    rotation.RotateZ(azimuth)
    rotation.RotateX(-elevation)
    rotation.Translate(centre)
    rotationMatrix = slicer.util.arrayFromVTKMatrix(rotation.GetMatrix())

    matrices, rowWidths, rowBottom = {}, [], None
    for row in rows:
        cursor = 0.0  # screen-left edge of the next model, measured in -R (i.e. towards patient left)
        zLow, zHigh = np.inf, -np.inf
        for model, node in row:
            matrix = (rotationMatrix if model != "CT" or rotateCT else np.eye(4)).copy()
            points = _localPoints(node)
            x = points @ matrix[0, :3] + matrix[0, 3]
            z = points @ matrix[2, :3] + matrix[2, 3]
            matrix[0, 3] += -cursor - x.max()
            matrices[model] = matrix
            cursor += (x.max() - x.min()) + gapMm
            zLow, zHigh = min(zLow, z.min()), max(zHigh, z.max())
        rowWidths.append(cursor - gapMm)
        zShift = 0.0 if rowBottom is None else rowBottom - gapMm - zHigh
        rowBottom = zLow + zShift
        for model, _ in row:
            matrices[model][0, 3] += rowWidths[-1] / 2  # centre the row on x = 0
            matrices[model][2, 3] += zShift
    for model, node in nodes:
        name = "ExampleCaseFigure offset " + model
        transformNode = slicer.mrmlScene.GetFirstNodeByName(name) or \
            slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", name)
        transformNode.SetMatrixTransformToParent(slicer.util.vtkMatrixFromArray(matrices[model]))
        node.SetAndObserveTransformNodeID(transformNode.GetID())

    layoutManager = slicer.app.layoutManager()
    layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView)
    threeDWidget = layoutManager.threeDWidget(0)
    viewNode = threeDWidget.mrmlViewNode()
    viewNode.SetRenderMode(slicer.vtkMRMLViewNode.Orthographic)
    viewNode.SetBoxVisible(False)
    viewNode.SetAxisLabelsVisible(False)
    viewNode.SetOrientationMarkerType(slicer.vtkMRMLAbstractViewNode.OrientationMarkerTypeNone)
    if background == "white":
        viewNode.SetBackgroundColor(1, 1, 1)
        viewNode.SetBackgroundColor2(1, 1, 1)
    else:  # Slicer's default gradient, as a newly created view node has it
        defaults = slicer.vtkMRMLViewNode()
        viewNode.SetBackgroundColor(defaults.GetBackgroundColor())
        viewNode.SetBackgroundColor2(defaults.GetBackgroundColor2())
    threeDWidget.threeDView().lookFromViewAxis(ctk.ctkAxesWidget.Anterior)
    fitCamera([m for m, _ in nodes])
    return json.dumps({
        "rows": [[m for m, _ in row] for row in rows],
        "rotation_deg": {"azimuth": azimuth, "elevation": elevation, "centre_mm": [round(c) for c in centre]},
        "rowWidths_mm": [round(w, 1) for w in rowWidths],
        "background": [viewNode.GetBackgroundColor(), viewNode.GetBackgroundColor2()],
        **_memory(),
    })


def fitCamera(order=None, margin=0.03, sizeFrom=None):
    """Fit the orthographic camera to the transformed surfaces, keeping the current view direction.

    The renderer's own ResetCamera fits a bounding sphere, which leaves a wide row tiny in the middle.
    The view is centred on `order` and scaled to fit the largest of the model lists in `sizeFrom`
    (default: just `order`), so rows captured one at a time come out at the same scale.
    """
    order = order or _defaultOrder()
    threeDView = slicer.app.layoutManager().threeDWidget(0).threeDView()
    width, height = threeDView.width, threeDView.height
    bounds = _groupBounds(order)
    halfHeight = 0.0
    for group in sizeFrom or [order]:
        groupBounds = bounds if group == order else _groupBounds(group)
        halfHeight = max(halfHeight, (groupBounds[5] - groupBounds[4]) / 2,
                         (groupBounds[1] - groupBounds[0]) / 2 * height / width)
    centre = [(bounds[0] + bounds[1]) / 2, (bounds[2] + bounds[3]) / 2, (bounds[4] + bounds[5]) / 2]

    renderer = threeDView.renderWindow().GetRenderers().GetFirstRenderer()
    camera = renderer.GetActiveCamera()
    position, focalPoint = camera.GetPosition(), camera.GetFocalPoint()
    camera.SetFocalPoint(centre)
    camera.SetPosition([centre[i] + position[i] - focalPoint[i] for i in range(3)])
    camera.SetParallelScale(halfHeight * (1 + margin))
    renderer.ResetCameraClippingRange()
    threeDView.forceRender()
    return json.dumps({"bounds_mm": [round(b) for b in bounds], "view_px": [width, height]})


def _groupBounds(order):
    box = vtk.vtkBoundingBox()
    for model in order:
        node = _node(model)
        if node:
            box.AddBounds(_worldBounds(node))
    bounds = [0.0] * 6
    box.GetBounds(bounds)
    return bounds


def _worldBounds(node):
    """Bounds of the surface points after the node's transform (bounding-box corners overestimate rotated shapes)."""
    matrix = vtk.vtkMatrix4x4()
    transformNode = node.GetParentTransformNode()
    if transformNode:
        transformNode.GetMatrixTransformToWorld(matrix)
    matrix = slicer.util.arrayFromVTKMatrix(matrix)
    points = _localPoints(node) @ matrix[:3, :3].T + matrix[:3, 3]
    low, high = points.min(axis=0), points.max(axis=0)
    return [low[0], high[0], low[1], high[1], low[2], high[2]]


def capture(path, hidePanel=True, models=None, sizeFrom=None):
    """Save the 3D view as a PNG and return each model's horizontal extent in it, as fractions of the image.

    With `models`, only those are shown and the view is centred on them, so that the rows of a
    multi-row layout can each be captured at the full width of the view; `sizeFrom` goes to
    fitCamera, to give every row the same scale. Hiding the module panel widens the view, which is
    the only way to more pixels: the capture scale factor does not work in Slicer
    (discourse.slicer.org/t/29341).
    """
    import ScreenCapture

    allModels = _defaultOrder()
    order = models or allModels
    hidden = [_node(m).GetDisplayNode() for m in allModels if m not in order]
    hidden = [d for d in hidden if d.GetVisibility()]
    panel = slicer.util.mainWindow().findChild(qt.QDockWidget, "PanelDockWidget")
    hidePanel = hidePanel and panel is not None and panel.isVisible()
    if hidePanel:
        panel.hide()
    for displayNode in hidden:
        displayNode.SetVisibility(False)
    try:
        slicer.app.processEvents()
        fitCamera(order, sizeFrom=sizeFrom)
        threeDView = slicer.app.layoutManager().threeDWidget(0).threeDView()
        renderWindow = threeDView.renderWindow()
        renderer = renderWindow.GetRenderers().GetFirstRenderer()
        width, height = renderWindow.GetSize()

        def toImage(x, y, z):
            renderer.SetWorldPoint(x, y, z, 1)
            renderer.WorldToDisplay()
            displayX, displayY = renderer.GetDisplayPoint()[0:2]
            return displayX / width, 1 - displayY / height  # image rows run top-down

        slots, zMin, zMax = [], [], []
        for model in order:
            bounds = _worldBounds(_node(model))
            yMid = (bounds[2] + bounds[3]) / 2
            left = toImage(bounds[0], yMid, bounds[4])[0]
            right = toImage(bounds[1], yMid, bounds[4])[0]
            # Patient right is on the viewer's left, so +x maps to smaller image x
            slots.append({"model": model, "x0": min(left, right), "x1": max(left, right)})
            zMin.append(bounds[4])
            zMax.append(bounds[5])
        rowTop = toImage(0, 0, max(zMax))[1]
        rowBottom = toImage(0, 0, min(zMin))[1]
        ScreenCapture.ScreenCaptureLogic().captureImageFromView(threeDView, path)
    finally:
        for displayNode in hidden:
            displayNode.SetVisibility(True)
        if hidePanel:
            panel.show()
        slicer.app.processEvents()
        fitCamera(allModels)
    return json.dumps({"size_px": [width, height], "rowTop": rowTop, "rowBottom": rowBottom, "slots": slots},
                      indent=1)
