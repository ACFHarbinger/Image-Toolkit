# **Theoretical and Practical Frameworks for High-Fidelity Image Mosaicking: From Invariant Feature Descriptors to Deep 3D Geometric Reconstruction**

The technological evolution of image stitching—the process of combining multiple images with overlapping fields of view into a single, high-resolution panoramic representation—has transitioned from simple pixel-averaging techniques to sophisticated computational frameworks that address the fundamental challenges of parallax, radiometric inconsistency, and temporal artifacts.1 Achieving a "perfect stitch" requires the simultaneous resolution of three primary technical hurdles: geometric registration, radiometric calibration, and optimal composition.2 Geometric registration involves finding the precise spatial transformation that aligns scene features across disparate views, a task complicated by non-planar scenes and non-coaxial camera movements.4 Radiometric calibration addresses the variations in brightness and color caused by exposure settings, lens vignetting, and changing light conditions.7 Finally, composition techniques, including seam finding and blending, must navigate the complexities of moving objects and residual misalignments to prevent "ghosting" or double-images.10

Visual evidence of these failures is common in naive stitching implementations. For instance, an analysis of sequential frames in a vertical pan reveals significant lighting discontinuities and banding effects, often caused by varying exposure or uncompensated vignetting towards the image periphery.13 Furthermore, simple "stacking" or layering of frames containing moving subjects results in the pervasive "double-image" artifact, where multiple instances of a foreground character appear in the composite result due to a lack of intelligent seam selection.10 The modern computational photography pipeline addresses these issues through a combination of traditional geometric principles and emerging deep neural architectures.

## **Foundations of Image Registration: Feature Detection and Descriptor Matching**

The foundational step in any mosaicking pipeline is the establishment of robust correspondences between images.2 This process, known as registration, relies on the detection of salient "interest points" that remain stable across different viewpoints and lighting conditions.2

### **Traditional Keypoint Detection and Hand-Crafted Invariants**

Early computer vision methods utilized simple intensity-based operators to identify regions of interest. Hans Moravec, in 1977, introduced the concept of "points of interest" by measuring intensity variations in all directions, a precursor to the modern corner detector.2 However, these early operators lacked invariance to rotation and scale. The development of the Scale-Invariant Feature Transform (SIFT) by David Lowe revolutionized the field by offering a robust mathematical framework for feature extraction.16 SIFT operates in a scale-space constructed using a Difference of Gaussians (DoG) pyramid, identifying local extrema that represent stable features regardless of the image's resolution or distance from the camera.19

The SIFT descriptor is a 128-dimensional vector that captures the distribution of local gradient orientations around each keypoint, making it partially invariant to illumination changes.16 While SIFT provides high accuracy and robustness, its computational intensity often makes it unsuitable for real-time applications.20 In response, the Oriented FAST and Rotated BRIEF (ORB) algorithm was proposed as an efficient alternative.20 ORB utilizes the FAST (Features from Accelerated Segment Test) detector and the BRIEF (Binary Robust Independent Elementary Features) descriptor, adding a rotation-aware mechanism by calculating the intensity centroid of the feature patch.20

| Algorithm | Keypoint Detector | Descriptor Basis | Dimensionality | Best Application |
| :---- | :---- | :---- | :---- | :---- |
| SIFT | Difference of Gaussians | Gradient Histograms | 128 (Float) | High-precision panoramas |
| SURF | Hessian-based (Haar) | Integral Images | 64/128 (Float) | Faster than SIFT, robust |
| ORB | Oriented FAST | Binary Comparisons | 256 (Binary) | Real-time SLAM, Mobile |
| AKAZE | Non-linear Diffusion | M-SURF | Binary | Rotated/Blurred scenes |

Source: 20

### **Deep Learning-Based Feature Extraction and Matching**

Traditional features often fail in challenging environments characterized by low texture, repetitive patterns, or significant domain shifts (e.g., day-to-night transitions).25 Modern deep learning approaches, such as SuperPoint, employ a self-supervised convolutional neural network (CNN) to learn interest point detection and description simultaneously.25 SuperPoint generates a much denser distribution of stable feature points compared to SIFT or ORB, providing a more reliable foundation for registration in feature-sparse regions.25

Beyond extraction, the matching phase has seen a paradigm shift with the introduction of transformer-based networks like LightGlue.29 Unlike traditional matchers (e.g., Brute-Force or FLANN) that rely on Euclidean or Hamming distance in a high-dimensional space, LightGlue uses self-attention and cross-attention mechanisms to learn the contextual relationships between points.30 This allows the network to adaptively prune unmatchable points, significantly increasing the precision of the resulting homography.30 For example, the combination of SIFT with LightGlue has been shown to outperform traditional matchers in high-rotation and low-texture scenarios, such as UAV imagery or repetitive agricultural patterns.30

## **Geometric Transformations and the Parallax Dilemma**

After correspondences are established, the pipeline must estimate the geometric transformation required to warp the images into a common coordinate system.3

### **Global Homography and the Planar Assumption**

The standard mathematical model for image alignment is the homography, a ![][image1] matrix ![][image2] that represents a projective transformation between two planes.2 Under the assumption that the scene is roughly planar or that the camera rotates purely around its optical center, a homography can perfectly align two views.1 The relationship between points ![][image3] in the source and ![][image4] in the target is defined as:

![][image5]  
This model has 8 degrees of freedom and is typically solved using the Direct Linear Transform (DLT) combined with RANSAC (Random Sample Consensus) to exclude outlier matches.2 However, the global homography is fundamentally limited; it cannot account for parallax, which arises when the scene contains depth variations and the camera undergoes translation.1

### **Spatially Varying and Non-Rigid Warping**

Parallax results in "ghosting" or blurred artifacts because a single ![][image2] cannot align foreground and background elements simultaneously.1 To mitigate this, researchers developed spatially varying warping methods, most notably As-Projective-As-Possible (APAP) warping.1 APAP divides the image into a grid and estimates a local homography for each cell.34 This is achieved through a Moving Direct Linear Transform (MDLT), where the contribution of feature matches to a specific cell is weighted by their proximity to that cell's center.34

While APAP improves local alignment, it can lead to unnatural perspective distortions in non-overlapping regions.6 For example, straight lines may appear bent, or architectural structures may seem tilted.6 The Shape-Preserving Half-Projective (SPHP) warp addresses this by transitioning the transformation from a projective model in the overlap region to a similarity transform (rotation, translation, scaling) in the non-overlap region.12 This ensures that the original aspect ratio and perspective of the image content are preserved outside the area of intersection.34

| Warping Strategy | Model Type | Parallax Tolerance | Non-Overlap Distortion | Structural Integrity |
| :---- | :---- | :---- | :---- | :---- |
| Global Homography | Rigid / Parametric | Low | None | High |
| APAP (MDLT) | Mesh-based / Grid | High | High (Projective) | Low (Bending) |
| SPHP | Hybrid | Moderate | Low (Similarity) | Moderate |
| Multi-Homography | Layered | Moderate | Low | High (Planar) |

Source: 1

### **Deep 3D Reconstruction and Very Large Parallax (VLP)**

Traditional 2D warping methods often fail when the camera baseline is significant (the distance between viewpoints is large).36 In such "Very Large Parallax" (VLP) scenarios, the relative positions of objects change too drastically for mesh-based deformation to compensate.36 Advanced deep learning frameworks, such as PIS3R, adopt a deep 3D reconstruction approach.36 By using visual geometry grounded transformers (VGGT), these systems jointly recover camera intrinsics, extrinsics, and a dense 3D point cloud of the scene.36 Pixels are then reprojected onto a reference view based on their true 3D coordinates, maintaining geometric consistency and enabling downstream tasks like Structure-from-Motion (SfM).36

## **Radiometric Consistency: Vignetting and Exposure Compensation**

Achieving a perfect stitch is as much a radiometric problem as it is a geometric one. Lighting mismatches at the seams are primarily driven by vignetting and varying exposure gains.8

### **The Physics and Modeling of Vignetting**

Vignetting is the phenomenon of radial falloff in brightness from the image center to the corners.8 It impairs computer vision algorithms that rely on precise intensity data, such as shape-from-shading and image mosaicking.9 The falloff is caused by:

1. **Natural Vignetting (![][image6] law)**: Foreshortening of the lens aperture when viewed at an angle ![][image7] from the optical axis, reducing light by ![][image8].7  
2. **Optical Vignetting**: Internal blocking of light paths by the lens barrel or diaphragm.8  
3. **Mechanical Vignetting**: Physical obstruction by filters or hoods.14  
4. **Pixel Vignetting**: Angular sensitivity of digital sensors due to the depth of photon wells.8

Vignetting can be modeled empirically using a radial polynomial:

![][image9]  
where ![][image10] is the distance from the principal point.7 Correcting this is essential for seamless results; otherwise, overlapping regions will display a "scalloped" or banded appearance.13

### **Gain Compensation and Multi-Spline Methods**

Even with vignetting removed, images may have different exposure levels. Brown and Lowe (2007) proposed a global gain compensation method that treats the gain ![][image11] of each image as an unknown parameter in a global optimization problem.2 By minimizing the sum of squared differences between overlapping pixels after gain adjustment, the system equalizes the overall brightness.16

For complex scenes with varying illumination, multi-spline offset fields provide a more localized solution.48 Instead of a single global gain, a smoothly varying multiplicative or additive offset map is associated with each source image.48 Modeling multiplicative gain is often superior for panoramas because exposure and vignetting are inherently multiplicative processes.48 By representing these maps using low-dimensional splines, the system can solve for lighting corrections efficiently, often 5–10 times faster than traditional quadtree-based Poisson solvers.48

## **Optimal Composition: Seam Finding and Blending**

The final stage of the pipeline involves selecting a path through the overlap region (seam finding) and smoothing the transition (blending).2

### **Seam Optimization to Prevent Ghosting**

"Ghosting" occurs when objects move between captures, creating double-images if the images are simply averaged.4 Seam-finding algorithms seek a path where the difference between images is minimal, effectively "cutting" around moving objects or misalignments.4

Dynamic Programming (DP) is a classic approach for finding optimal seams in linear time.50 By calculating an energy map—often based on intensity and gradient differences—DP backtracks to find the path with the lowest cumulative cost.52 However, traditional DP and Graph-Cut methods often lack semantic awareness, resulting in seams that cut through foreground objects (e.g., people, vehicles), as seen in many "stacking" artifacts.37 The SemanticStitch framework addresses this by incorporating semantic priors to protect foreground object integrity, ensuring that seams bypass critical areas.50

### **Blending and Fusion Domains**

Once a seam is defined, blending is used to make the transition invisible. Naive blending (feathering) averages pixels in a transition window, which can cause blur if alignment is imperfect.4 Multi-band blending mitigates this by decomposing the image into a Laplacian pyramid.4 Low-frequency components are blended over a large area to smooth illumination differences, while high-frequency components are blended over a narrow area to preserve sharp texture and prevent ghosting.4

Poisson blending (gradient domain) offers superior results by ensuring that the gradient field of the composite is consistent with the sources.6 By solving the Poisson equation:

![][image12]  
where ![][image13] is the target gradient field, the algorithm produces a composite where intensity offsets are smoothly distributed, virtually eliminating visible seams even under significant lighting mismatches.48

| Blending Method | Operational Domain | Main Strength | Computational Load |
| :---- | :---- | :---- | :---- |
| Feathering | Spatial Intensity | Simplicity | Negligible |
| Multi-band | Laplacian Pyramid | Texture Preservation | Moderate |
| Poisson Blending | Gradient Field | Seamless Illumination | High |
| Multi-Spline | Offset Map Splines | Fast Exposure Correction | Moderate |

Source: 4

## **Modern Neural Approaches and Automated Refinement**

The integration of deep learning has led to end-to-end models that automate many of the traditionally hand-tuned steps in the stitching pipeline.26

### **Unsupervised Homography and Flow Matching**

Standard supervised homography estimation relies on synthetic data or aerial images with known poses.56 Newer unsupervised frameworks, like UDRSIS for remote sensing or HomoFM, learn features specific to the dataset by minimizing pixel-wise intensity errors or velocity fields.27 These models are more robust to noise and illumination variation than traditional feature-based approaches.56 Some architectures, such as the HomoFormer, utilize SIFT-guided curriculum learning to boost the alignment's ability to handle extreme geometric distortions.59

### **Deep Image Rectangling and Diffusion Refinement**

Panoramic images often have irregular, "wavy" boundaries due to projection effects.39 Deep image rectangling replaces traditional cropping or manual warping by predicting a content-aware mesh that transforms the irregular shape into a rectangle while preserving content fidelity.39 This one-stage solution is significantly more efficient than previous two-stage optimization baselines.39 Furthermore, diffusion-based fusion networks now use pixel-wise confidence maps to define adaptive blending regions, effectively suppressing residual ghosting artifacts in high-parallax scenes that traditional blending cannot resolve.12

## **Addressing Anime Panning and Stacking Artifacts: A Synthesis**

The "perfect stitch" in specialized domains like anime production faces unique challenges. Anime often utilizes long vertical or horizontal pans of static backgrounds with characters moving in the foreground.61

### **Solving Lighting Mismatches in Pans**

As observed in vertical pan sequences, visible horizontal bands often occur where lighting changes frame-by-frame.13 Traditional "stacking" of these frames without exposure adjustment fails because the camera's auto-exposure or changing lens angles cause intensity shifts.14 The solution involves pre-processing with vignetting correction (using either a flat-field image or polynomial model) followed by robust gain compensation.7 Microsoft Image Composite Editor (ICE) and automated tools like PTGui utilize these techniques to equalize illumination even when it changes significantly with every frame.13

### **Eliminating Double-Images in Dynamic Scenes**

The "double-image" issue, prominent when sequential character movements are "stacked," is a direct consequence of inadequate seam selection.10 To resolve this, a "vertex cover" or "object-aware" seam algorithm must be employed.11 This ensures that for any region of difference (ROD), only one instance of the foreground object is selected from the set of overlapping frames.11 In manual workflows, this is often "hacked" by lowering the opacity of layers to align them and then using clone-stamping or masks to remove the ghosted elements.61 Automated systems now achieve this by calculating an optimal seam that follows the boundaries of moving objects, ensuring they are either completely included or excluded from a specific source image.10

## **Conclusion: The Integrated Roadmap to Perfection**

The technical path to a perfect, artifact-free stitch is no longer a matter of choosing a single algorithm, but rather orchestrating a multi-stage computational pipeline. Modern excellence in image mosaicking is characterized by:

1. **Context-Aware Registration**: Moving beyond hand-crafted features to learned descriptors like SuperPoint and contextual matchers like LightGlue to ensure dense, accurate correspondences even in feature-sparse anime backgrounds.25  
2. **Adaptive Geometric Warping**: Utilizing hybrid models like SPHP or deep 3D reconstruction (PIS3R) to handle depth disparities and parallax without introducing global stretching distortions.34  
3. **Rigorous Radiometric Pre-processing**: Prioritizing vignetting and exposure correction as first-class citizens in the pipeline to prevent the banding and lighting mismatches seen in panoramic pans.8  
4. **Semantic Seam Optimization**: Leveraging deep learning to identify and protect foreground objects, ensuring that seams do not create the "double-image" or "broken structure" artifacts common in dynamic scene stacking.11  
5. **Multi-Scale Gradient Blending**: Employing Poisson or multi-band blending to hide residual seams, providing the final layer of visual seamlessness.4

By synthesizing these traditional geometric certainties with the probabilistic power of deep neural networks, computational photography can now achieve composite images that are structurally, radiometrically, and semantically indistinguishable from a single, expansive viewport.

#### **Works cited**

1. Image Stitching Based on Nonrigid Warping for Urban Scene \- MDPI, accessed April 29, 2026, [https://www.mdpi.com/1424-8220/20/24/7050](https://www.mdpi.com/1424-8220/20/24/7050)  
2. Image stitching \- Wikipedia, accessed April 29, 2026, [https://en.wikipedia.org/wiki/Image\_stitching](https://en.wikipedia.org/wiki/Image_stitching)  
3. Image Alignment and Stitching: A Tutorial \- Computer Sciences User Pages, accessed April 29, 2026, [https://pages.cs.wisc.edu/\~dyer/cs534/papers/szeliski-alignment-tutorial.pdf](https://pages.cs.wisc.edu/~dyer/cs534/papers/szeliski-alignment-tutorial.pdf)  
4. Parallax-tolerant Image Stitching \- The Computer Vision Foundation, accessed April 29, 2026, [https://openaccess.thecvf.com/content\_cvpr\_2014/papers/Zhang\_Parallax-tolerant\_Image\_Stitching\_2014\_CVPR\_paper.pdf](https://openaccess.thecvf.com/content_cvpr_2014/papers/Zhang_Parallax-tolerant_Image_Stitching_2014_CVPR_paper.pdf)  
5. Structure Preservation and Seam Optimization for Parallax-Tolerant Image Stitching \- IEEE Xplore, accessed April 29, 2026, [http://ieeexplore.ieee.org/iel7/6287639/9668973/09841552.pdf](http://ieeexplore.ieee.org/iel7/6287639/9668973/09841552.pdf)  
6. Robust image stitching method with line preservation and seamless blending, accessed April 29, 2026, [https://opg.optica.org/ao/fulltext.cfm?uri=ao-64-29-8682](https://opg.optica.org/ao/fulltext.cfm?uri=ao-64-29-8682)  
7. EP1447977A1 \- Vignetting compensation \- Google Patents, accessed April 29, 2026, [https://patents.google.com/patent/EP1447977A1/en](https://patents.google.com/patent/EP1447977A1/en)  
8. Vignette and Exposure Calibration and Compensation \- University of Washington, accessed April 29, 2026, [https://grail.cs.washington.edu/projects/vignette/vign.iccv05.pdf](https://grail.cs.washington.edu/projects/vignette/vign.iccv05.pdf)  
9. Single-Image Vignetting Correction \- Microsoft, accessed April 29, 2026, [https://www.microsoft.com/en-us/research/wp-content/uploads/2009/12/pami09zheng.pdf](https://www.microsoft.com/en-us/research/wp-content/uploads/2009/12/pami09zheng.pdf)  
10. Parallax-Robust Surveillance Video Stitching \- MDPI, accessed April 29, 2026, [https://www.mdpi.com/1424-8220/16/1/7](https://www.mdpi.com/1424-8220/16/1/7)  
11. Eliminating Ghosting and Exposure Artifacts in Image Mosaics, accessed April 29, 2026, [https://www.cs.jhu.edu/\~misha/ReadingSeminar/Papers/Uyttendaele01.pdf](https://www.cs.jhu.edu/~misha/ReadingSeminar/Papers/Uyttendaele01.pdf)  
12. Depth-Supervised Fusion Network for Seamless-Free Image Stitching \- arXiv, accessed April 29, 2026, [https://arxiv.org/html/2510.21396v1](https://arxiv.org/html/2510.21396v1)  
13. Vignetting correction \- PTGui Stitching Software, accessed April 29, 2026, [https://ptgui.com/examples/vigntutorial.html](https://ptgui.com/examples/vigntutorial.html)  
14. Vignetting | Scientific Volume Imaging, accessed April 29, 2026, [https://svi.nl/Vignetting](https://svi.nl/Vignetting)  
15. Moving Object Removal/ Motion Reconstruction in Stereo Panoramas, accessed April 29, 2026, [https://web.stanford.edu/class/ee368/Project\_Autumn\_1617/Reports/report\_yang\_wang\_wang.pdf](https://web.stanford.edu/class/ee368/Project_Autumn_1617/Reports/report_yang_wang_wang.pdf)  
16. Automatic Panoramic Image Stitching | PDF | Imaging | Teaching Mathematics \- Scribd, accessed April 29, 2026, [https://www.scribd.com/document/397784575/Lowe-2007](https://www.scribd.com/document/397784575/Lowe-2007)  
17. A comparative analysis of pairwise image stitching techniques for microscopy images \- PMC, accessed April 29, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC11035624/](https://pmc.ncbi.nlm.nih.gov/articles/PMC11035624/)  
18. Image Stitching \- Columbia CAVE, accessed April 29, 2026, [https://cave.cs.columbia.edu/Statics/monographs/Image%20Stitching%20FPCV-2-4.pdf](https://cave.cs.columbia.edu/Statics/monographs/Image%20Stitching%20FPCV-2-4.pdf)  
19. Automatic Panoramic Image Stitching using Invariant Features \- UBC Computer Science, accessed April 29, 2026, [https://www.cs.ubc.ca/\~lowe/papers/07brown.pdf](https://www.cs.ubc.ca/~lowe/papers/07brown.pdf)  
20. SIFT vs. ORB: Which Feature Detector Performs Best for Real-Time Applications?, accessed April 29, 2026, [https://eureka.patsnap.com/article/sift-vs-orb-which-feature-detector-performs-best-for-real-time-applications](https://eureka.patsnap.com/article/sift-vs-orb-which-feature-detector-performs-best-for-real-time-applications)  
21. Stitching and Blending, accessed April 29, 2026, [https://web.stanford.edu/class/cs231m/lectures/lecture-5-stitching-blending.pdf](https://web.stanford.edu/class/cs231m/lectures/lecture-5-stitching-blending.pdf)  
22. Comparing SIFT and ORB for Feature Matching: A Visual and Practical Exploration, accessed April 29, 2026, [https://medium.com/@beauc\_37732/comparing-sift-and-orb-for-feature-matching-a-visual-and-practical-exploration-6c194c72e4d6](https://medium.com/@beauc_37732/comparing-sift-and-orb-for-feature-matching-a-visual-and-practical-exploration-6c194c72e4d6)  
23. Comprehensive empirical evaluation of feature extractors in computer vision \- PMC \- NIH, accessed April 29, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC11623105/](https://pmc.ncbi.nlm.nih.gov/articles/PMC11623105/)  
24. Research on Image Stitching Based on an Improved LightGlue Algorithm | Scilit, accessed April 29, 2026, [https://www.scilit.com/publications/f463f2b731a60068d85bc1964f8dfa3a](https://www.scilit.com/publications/f463f2b731a60068d85bc1964f8dfa3a)  
25. Image Matching: Foundations, State of the Art, and Future Directions \- MDPI, accessed April 29, 2026, [https://www.mdpi.com/2313-433X/11/10/329](https://www.mdpi.com/2313-433X/11/10/329)  
26. DunHuangStitch: Unsupervised Deep Image Stitching of Dunhuang ..., accessed April 29, 2026, [https://www.computer.org/csdl/journal/tg/2025/08/10522976/1WMgBQmRflS](https://www.computer.org/csdl/journal/tg/2025/08/10522976/1WMgBQmRflS)  
27. HomoFM: Deep Homography Estimation with Flow Matching \- arXiv, accessed April 29, 2026, [https://arxiv.org/html/2601.18222](https://arxiv.org/html/2601.18222)  
28. Are learned interest point/feature detectors used much in industry for SLAM/ego-motion?, accessed April 29, 2026, [https://www.reddit.com/r/computervision/comments/1areks7/are\_learned\_interest\_pointfeature\_detectors\_used/](https://www.reddit.com/r/computervision/comments/1areks7/are_learned_interest_pointfeature_detectors_used/)  
29. Research on Image Stitching Based on an Improved LightGlue Algorithm \- MDPI, accessed April 29, 2026, [https://www.mdpi.com/2227-9717/13/6/1687](https://www.mdpi.com/2227-9717/13/6/1687)  
30. Robust UAV Image Mosaicking Using SIFT and LightGlue \- ResearchGate, accessed April 29, 2026, [https://www.researchgate.net/publication/397076090\_Robust\_UAV\_Image\_Mosaicking\_Using\_SIFT\_and\_LightGlue](https://www.researchgate.net/publication/397076090_Robust_UAV_Image_Mosaicking_Using_SIFT_and_LightGlue)  
31. third\_party/LightGlue/README.md · Realcat/image-matching-webui at 172c865839aac1b9231f9a44c39c922ab1214b53 \- Hugging Face, accessed April 29, 2026, [https://huggingface.co/spaces/Realcat/image-matching-webui/blame/172c865839aac1b9231f9a44c39c922ab1214b53/third\_party/LightGlue/README.md](https://huggingface.co/spaces/Realcat/image-matching-webui/blame/172c865839aac1b9231f9a44c39c922ab1214b53/third_party/LightGlue/README.md)  
32. Robust UAV Image Mosaicking Using SIFT and LightGlue \- ISPRS \- The International Archives of the Photogrammetry, Remote Sensing and Spatial Information Sciences, accessed April 29, 2026, [https://isprs-archives.copernicus.org/articles/XLVIII-2-W11-2025/169/2025/isprs-archives-XLVIII-2-W11-2025-169-2025.pdf](https://isprs-archives.copernicus.org/articles/XLVIII-2-W11-2025/169/2025/isprs-archives-XLVIII-2-W11-2025-169-2025.pdf)  
33. Image Alignment and Stitching: A Tutorial1 \- Carnegie Mellon Graphics, accessed April 29, 2026, [http://graphics.cs.cmu.edu/courses/15-463/2004\_fall/www/Papers/MSR-TR-2004-92-Sep27.pdf](http://graphics.cs.cmu.edu/courses/15-463/2004_fall/www/Papers/MSR-TR-2004-92-Sep27.pdf)  
34. (PDF) IMAGE STITCHING WITH PERSPECTIVE-PRESERVING WARPING \- ResearchGate, accessed April 29, 2026, [https://www.researchgate.net/publication/307531734\_IMAGE\_STITCHING\_WITH\_PERSPECTIVE-PRESERVING\_WARPING](https://www.researchgate.net/publication/307531734_IMAGE_STITCHING_WITH_PERSPECTIVE-PRESERVING_WARPING)  
35. Image Alignment and Stitching \- Faculty, accessed April 29, 2026, [https://www.cmor-faculty.rice.edu/\~zhang/caam699/p-files/Im-Align2005.pdf](https://www.cmor-faculty.rice.edu/~zhang/caam699/p-files/Im-Align2005.pdf)  
36. arxiv.org, accessed April 29, 2026, [https://arxiv.org/html/2508.04236v3](https://arxiv.org/html/2508.04236v3)  
37. NeurIPS Poster Depth-Supervised Fusion Network for Seamless-Free Image Stitching, accessed April 29, 2026, [https://neurips.cc/virtual/2025/poster/115047](https://neurips.cc/virtual/2025/poster/115047)  
38. Wide parallax image stitching with balanced alignment-naturalness \- IEEE Xplore, accessed April 29, 2026, [https://ieeexplore.ieee.org/iel8/6287639/6514899/11000324.pdf](https://ieeexplore.ieee.org/iel8/6287639/6514899/11000324.pdf)  
39. Deep Rectangling for Image Stitching: A Learning Baseline \- CVF Open Access, accessed April 29, 2026, [https://openaccess.thecvf.com/content/CVPR2022/papers/Nie\_Deep\_Rectangling\_for\_Image\_Stitching\_A\_Learning\_Baseline\_CVPR\_2022\_paper.pdf](https://openaccess.thecvf.com/content/CVPR2022/papers/Nie_Deep_Rectangling_for_Image_Stitching_A_Learning_Baseline_CVPR_2022_paper.pdf)  
40. PIS3R: Very Large Parallax Image Stitching via Deep 3D Reconstruction \- arXiv, accessed April 29, 2026, [https://arxiv.org/html/2508.04236v1](https://arxiv.org/html/2508.04236v1)  
41. Single-Image Vignetting Correction, accessed April 29, 2026, [https://www.eecis.udel.edu/\~jye/lab\_research/09/JiUp.pdf](https://www.eecis.udel.edu/~jye/lab_research/09/JiUp.pdf)  
42. Image Shading | ISO 17957 | Image Quality Factors, accessed April 29, 2026, [https://www.image-engineering.de/library/image-quality/factors/1073-shading](https://www.image-engineering.de/library/image-quality/factors/1073-shading)  
43. Vignetting \- PanoTools.org Wiki, accessed April 29, 2026, [https://wiki.panotools.org/Vignetting](https://wiki.panotools.org/Vignetting)  
44. Image Vignetting Correction Using a Deformable Radial Polynomial Model \- PMC, accessed April 29, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC9921563/](https://pmc.ncbi.nlm.nih.gov/articles/PMC9921563/)  
45. Vignetting \- Informatics Homepages Server, accessed April 29, 2026, [https://homepages.inf.ed.ac.uk/rbf/CVonline/LOCAL\_COPIES/AV0809/laskaris.pdf](https://homepages.inf.ed.ac.uk/rbf/CVonline/LOCAL_COPIES/AV0809/laskaris.pdf)  
46. Automatic Panoramic Image Stitching using Invariant Features | Request PDF, accessed April 29, 2026, [https://www.researchgate.net/publication/225133245\_Automatic\_Panoramic\_Image\_Stitching\_using\_Invariant\_Features](https://www.researchgate.net/publication/225133245_Automatic_Panoramic_Image_Stitching_using_Invariant_Features)  
47. Image Stitching with OpenCV and Python \- PyImageSearch, accessed April 29, 2026, [https://pyimagesearch.com/2018/12/17/image-stitching-with-opencv-and-python/](https://pyimagesearch.com/2018/12/17/image-stitching-with-opencv-and-python/)  
48. Fast Poisson Blending using Multi-Splines \- Microsoft, accessed April 29, 2026, [https://www.microsoft.com/en-us/research/wp-content/uploads/2011/04/Szeliski-ICCP11.pdf](https://www.microsoft.com/en-us/research/wp-content/uploads/2011/04/Szeliski-ICCP11.pdf)  
49. Image Blending in Gradient Domain, accessed April 29, 2026, [https://pavancm.github.io/pdf/AIP\_Mid\_Report.pdf](https://pavancm.github.io/pdf/AIP_Mid_Report.pdf)  
50. SemanticStitch: Enhancing Image Coherence through Foreground-Aware Seam Carving, accessed April 29, 2026, [https://arxiv.org/html/2511.12084v2](https://arxiv.org/html/2511.12084v2)  
51. Project: Seam Carving, accessed April 29, 2026, [https://blackruan.github.io/seam-carving/](https://blackruan.github.io/seam-carving/)  
52. How Seam Carving Uses Dynamic Programming to Preserve What Matters | by Tanish Singla | Medium, accessed April 29, 2026, [https://medium.com/@tanishsingla125/how-seam-carving-uses-dynamic-programming-to-preserve-what-matters-6edb9f49e384](https://medium.com/@tanishsingla125/how-seam-carving-uses-dynamic-programming-to-preserve-what-matters-6edb9f49e384)  
53. Implementing Seam Carving for Image Resizing \- cs.wisc.edu, accessed April 29, 2026, [https://pages.cs.wisc.edu/\~moayad/cs766/](https://pages.cs.wisc.edu/~moayad/cs766/)  
54. Image blending, accessed April 29, 2026, [http://graphics.cs.cmu.edu/courses/15-463/2017\_fall/lectures/lecture7.pdf](http://graphics.cs.cmu.edu/courses/15-463/2017_fall/lectures/lecture7.pdf)  
55. Image Stitching algorithm in Python from scratch with gain compensation and blending \- GitHub, accessed April 29, 2026, [https://github.com/CorentinBrtx/image-stitching](https://github.com/CorentinBrtx/image-stitching)  
56. (PDF) Unsupervised Deep Homography: A Fast and Robust ..., accessed April 29, 2026, [https://www.researchgate.net/publication/319662477\_Unsupervised\_Deep\_Homography\_A\_Fast\_and\_Robust\_Homography\_Estimation\_Model](https://www.researchgate.net/publication/319662477_Unsupervised_Deep_Homography_A_Fast_and_Robust_Homography_Estimation_Model)  
57. JirongZhang/DeepHomography: Content-Aware Unsupervised Deep Homography Estimation \- GitHub, accessed April 29, 2026, [https://github.com/JirongZhang/DeepHomography](https://github.com/JirongZhang/DeepHomography)  
58. Unsupervised Deep Homography: A Fast and Robust Homography Estimation Model \- arXiv, accessed April 29, 2026, [https://arxiv.org/abs/1709.03966](https://arxiv.org/abs/1709.03966)  
59. Unsupervised Deep Image Stitching for Remote Sensing: Aligning Features Across Large-Scale Geometric Distortions \- ResearchGate, accessed April 29, 2026, [https://www.researchgate.net/publication/395561017\_Unsupervised\_Deep\_Image\_Stitching\_for\_Remote\_Sensing\_Aligning\_Features\_Across\_Large-Scale\_Geometric\_Distortions](https://www.researchgate.net/publication/395561017_Unsupervised_Deep_Image_Stitching_for_Remote_Sensing_Aligning_Features_Across_Large-Scale_Geometric_Distortions)  
60. \[2203.03831\] Deep Rectangling for Image Stitching: A Learning Baseline \- arXiv, accessed April 29, 2026, [https://arxiv.org/abs/2203.03831](https://arxiv.org/abs/2203.03831)  
61. How do i make anime stitches? \- Reddit, accessed April 29, 2026, [https://www.reddit.com/r/anime/comments/2177wf/how\_do\_i\_make\_anime\_stitches/](https://www.reddit.com/r/anime/comments/2177wf/how_do_i_make_anime_stitches/)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACsAAAAXCAYAAACS5bYWAAACm0lEQVR4XrVVT4hPURQ+F6HkT0NhsLSwkNI0CyVKKVvZWVFKrC2QhWTBArGxUNMsMGVmY6MspFEsDImthQ0KJYQkje+8c9/9d+599/3y89X3+73zne+ee959975HxDDNb28U7cVEP/jhuUKRljNo9HNpXxoPDQMXVgOUoNFalFUJQ0Zn/UKyIDcwXUnBUvAJ+BucBPeJ7AfGJYwT3CJV5qikW8ME+Al8AJ5Mk4w74HufoK3gPHjFS9WpNPz9dMA5tpPMucRljJlC+jsuN7Qa4yeJcb2NF4K/Ghpa1mPGYeAUSQ+XA+201c4FGq1FP8eCpnCXhk38KGoYx7jR+IaiYBM4FwoOehH2kixUixkjze4JNIXzJKYxL+nKFpx4Ba5JExYvwMOpKMjVFA2/K/H3g2SLZsENzsP4nBpzrlhW5dW4By4OtBHwaRvw4cuMU4DnIX6aPhAdSvMhdlt+BF9HmTqWgzPgIhs/xsQ3XYc9OrWWbSQ9XAP/gOucoYBxkgN2KU10w8xhxmlcrAKnjW+cc/6yHxaQ3Pw7cEuUyZS6TrItbqSJDvCj58P0gXhLZIp6dCZbbCS7NUPxKnghFIAzJKZZCbuKu2fNjbYre5fCla0PPwjejhMNVLNKIPmKsXY20XPgk/uI9AHj5oOtEEA33/Ygj1zym0leoV+di8T0li9sDT7db8Av5D8UCsF83OiUDx1Wg7dI9l+EuNcm+kx6wY5a7WIojoL3SRqeJXl1yGtHr0CKXRR8Iht/PIY/Cs8ipYzjJO/WlyQH/Bu4InIEOACeAHdwUO9TQ41RQhU7wSMYuB8v59KHpgNuwvzMqZrGWfQyDYhBa/b19/Wxsbf3/2EYLRRqxHLB9K8olS3pOdS8Ll8xcrpiSRC7/wLpxmG9PKLLaAAAAABJRU5ErkJggg==>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAAYCAYAAAD3Va0xAAABNElEQVR4XqWUTUoDQRCFq/ECLswBFNwpeITBpcvgAbLJKicQdOMBvEHIIisvIt4jwbWuhEBIqqeqpu36mQ74QdOZ995UV3cPgQSZBDLX6Od/EJUSfWggCvqMpEesHn/LsS48oXUAM9I5+wfx/+R+2cvUO4YS9LgA8t7zQ6szLmQDqLyxf+v5ipRX/NYqv/iJ48uUMALADKj1F6VnHoA6XdRycgutgArdF2lIvbJ3Uzyfa6DgB77a4dzJzGPPPuO0wdIcqPXnyhxIwW2araUtB89I1yv2hTZKzLr5KR+ZKYFMgLy1Nhz6a3da71kCfT/5HBn51yh0OB5LoZSfL9m7wzHF8YP6jrNX7J2KrBfNgj2jJv4lNLFnoAn901YsfpDXZ6DnEaJIpGtUrn0WmjrffLsZGDgCyso4AMbGlKgAAAAASUVORK5CYII=>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAaCAYAAABhJqYYAAABHklEQVR4XoVTS2oCQRCtXgmCS0FEhNm5yi5XCLmAWXgJzyEIkl28RPQIgazcBLIMzBkiCm6yia+6+m/1+OBNdVW96n7TzJAhgY8RUjFlI8+Vbn1Hj1QRVFGuDdoavGQ9TRjAxm/MW3iPFaOSqsV7yP2FzJtPgq3l9vQjJuARbMFXsAfdFvELfE5HpuAPOITgCY0z1u/gCuSBS1Ci+Vmc9g0unIV/8EPKImoksRiRCMaxZKL17P0NvZGIK6+WAILWOLHDAHz0kxy4uQPXvEbhL0iJTuBDyHg3hBlWfCMbkuE+OEftxWnC80CyW+NOW4K/4L7qW23EW3BRVamISr5CzopP/c6Radekw9mUJOpGOZykW6mIugcEpQn7n4aM6AqUCB+ybBko0AAAAABJRU5ErkJggg==>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAYCAYAAADzoH0MAAABO0lEQVR4XpWSP0oEMRSHE2QLy8XKxU7QyspGxLUSvIEHUPEUFhZ2gq0nsNMbiBew2FKtFsRCsbbQZv0mm0nevLww7ge/JO9f5iUZ53rwau6lW7BA+T9SBF59QJTbG7UFgU00w94xsw2XU95jNPV2aq2T3AHzK+PIaL60DM8R9kwdqUEXajtxjb5zXOSxHDK+sfxiHkf3C/pEy9H+QdtxLfErDE9oHW2hX3SFVtE+uoyJh3GO5Jt4ZhiIAOd0t2gNfWAf5JiJ35jvlX6Q5p1PRLz1Z1dLtzBwhqYymjEuz+AO3cyXKXGobE1oecLi1IV3drsx0NzLY0oryBs2z7eH4535HF2gJfSA7lNWvYNM95TFH1fYvVRvPyD8OlF3UNuiil2gPyAWdkGLUWhTC9f8C9DttNiwcBTYhd79AU+ZIDPIouqnAAAAAElFTkSuQmCC>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAA+CAYAAACWTEfwAAAItUlEQVR4Xu3df4ilVR3H8e9kaZZFK1vGEkVrRX8YRkqZmAxRGYlR7PaDFNxCKi0iRAiNZPOf1Mwloz+MyKCkoNKUkigsipLVIDbLPypoFn9UkhQoKiZR58M5x/neM+fOzLn3eZ5779z3Cw7Pec65c8+dZ3fm+dznPHOPGQAAAAAAAAAAAAAAAAAAANBspWwAAADA9hCkAAAAsIMRd7fCEQIAAAAAAAAAAAAAAACAJfRUKP9L5adFH6L9tn6MVH432o2MOxEBAOiHAlvpAYvBZAgXWxzr9LKjB8dYHOvWsqPBbluiwEYAA4wfBABzoRbYZKjAJjeUDT16cShnlY0NliqwAQCAebAyF4FtyLGOlA2NCGwAAGBwtcC2L5T/hHJbKPcWfX1QYDsUyiNlRw801gGLY50w2rUtBLa5x/wVAGDnqQU2hZo7Uv2tFu/96st1FsNhdtDVu7bLRq/mTXJlj8AGbIK4jIXBf1YsmHGBLbvF1U+y0Rv2Tw3lQbc/iadDOS/VTwvl5FR/TiifSXU5GspLQvmma2t1TSiH3f5Nrv5OV/+axR/l/7q2jMAGAAAGt1Vgy/U9afvn3JFMcpXKq411adpemDtsvW+a8fS1J6Z6voJ4c9p6+TG1sQhsAABgcLXAdn3anm3xKtOdrq/vwLZq8S85xQe27G9lQ4NyLLnKtXnftnhFr0RgAwAAAxv/V6LjdB3YNlMGtrVivy+a6hXdW/cW32EENgAAMAOLEth+lrbvcW198dOvL/QdRmADAAAz0BrYlh2BDYPgD9gAAB6BrQ2BbWgkl95xiAGgZx38oiWwtSGwYYMOfg4BANjU7APbYp3tCGyYC4v1YwNgSH3eXI7ZmX1gWywhsK0Q2ABgqSzOW6TzQ/l62TilVYsfWvoTi8sf5TYFww+l/aF80eYnkL7b4ms5N+2vhvKYxQ+TVb1r4wLbkMfjhrKhR/qMt7PKxgZcYQMAzK0j1k+8vC+U5xZtWqpoFoYMKJtRWC1fS7nfpXkIbEOONW043B1+EghsAIC59IOyoSPlifpqW7+yNLT8WvQ5X2WIPBDKm1P9+FDeFcpLQ/lUfkDyEZs+2Cqw3uX2T7CNx6lDK7XAts/ih8beFsq9RV8f9P0dCuWRsqMHGuuAxbF0bFtxhQ0AMHOvCOVGi1Nwmq7Usj1+UewuKfiUQUQhoaSpwFtC+Vcoby/6tksB5DcWT9D6/rQIuGj8i1z9x66eaSHwY0I5w+LUbQ5QD6TtZ0PZlepSfk+t9PX+w2EPprZ+1Fc6+K2NBtg+6fn99/dpV++DxtLC8jJJQCSwAcBONe0llwHlk7OC0zmhXO76xtEJcH8ofyw7tqB717ROpVcGk++n7RfSVle2JpWfW1fB7k71vMi4+LFVP9nivU5luzweyieL9tel+l6rr0G5XeUx0P71RVuXaoHNvwaF5ex9aZv7tfpA+Xpb6Yrieal+msXjLgqNkp+/HHsSCuqH3f5NaXt72v7K4lJUGuPYtC0R2AAAc6N2oqr5QLGvoPesVL/fd1RojC+7fZ2sx41bu/LWSs+9x2JAqY3j21R/VSifSPVVV0SB7YOpLnqMwu5qKuWUaovytWn/xKKtS1sFtlq91jYp//Vrrp7bH7QY4mpjt1I4fG+qX2jxKq/oaukbQvmYxRCXj3dtLAIbAGDmypPixbljjHFBIp8IR41eaixPhv8I5S9FW/l6np07JqCApefR1a8f2sZAWYaQ11ba8718T1qcZs20vqYPn69x9RZX2GgQlPI4lVY3KcfpAVuoBbZ8Re9si1dB73R98kZX3+r1baU87qsW/5Iz+46rix+7VTmWXOXaHnV1+XuxLwQ2AMDMaYrr4xZPZi+y9fu7uqSQd4nFMXI40b1p2tc9ZLpfLFObpsZ0r9ErQ/mD65tEPkm/wNVF9+lpX1dfXpbq30h9urrzI4v3r2mKNN/D9j1bvxdKFDg/Gsplrq2FjsUTFqda9b2+3uKUtALTO9zjulYGNh0bH7g1hbjX7a+5ukwb2Hzw/aqNTjXrDxG8cuxW+nfM9O+Zp0JFV1SzU9NWV3Y1ReoR2IChLdB9RcDcqf78VBsx58rAthn9McrPbfTew2kD2zj/tPgGQtPPUhu7K1+xONbDFj9WRVupfW8ENgAAMLiWwAYCGwAAmAECW5sBAhuXqgEAwCgCW5sBAhsAAMAoAlsbAhsAABgcga0NgQ3YObj/AMDCqAW2vOzWEPRZfxrr9LKjB/rIGI11a9nRgMAGAFhSvMeZpVpgk6ECm/y+bOjR+23sBzBv6z8igQ0AlsW2TgvAMOYhsA051pGyoRGBDQAADGulHti0NNXRUC4wt7pET280tPKFAtuNoVwbyqtHuzunsf5kcTF5jdmKwAZgfvX0ixrA7NUCm0LNHamuJZzycmGrofzSRhe3P8nVJ3GdxSWgsoNpq3VQFay0nqnoHjetdnBs2p/ELhu9mufr94TyuVQvx/YIbAAAYGgr4wJbppCU5fZxoWcS+nqtzyqfd+0PWVyrNT//0bSdZrxfh/KlVH9+KPtT/YpQPmxxuvRM2zi2R2ADAACD2yqw5fqetH1eKKekutRCTYvaWJe6Nk3PyjlpO814+lpNwUq+gnhz2sqaq0se2yOwAUArpmqBqZWBTdOf56a6wsm/zd3HltRC1qTucnU91/1uP7flKdnaFGUL/1oftTgde7xr+67Fe9syP3ZGYAOwvAhewMyUgW0zOfB0GdjG8WO9zWJQ2hfKy595RHd0DPaGcmUov7CNY3sENgAAMLiWwHZ1KIdt/Z6zv1oMNYeeeUR33mTxxn/dUyYaJ5eu6XPZHg7l8rRfju0tXGDjDTEAAItPgW0tnNXXwvZbZSc22B2O1UIFNgDAIuLtNtBKf03qr/AR2LBY+L0PAAAAAAAAAAAAAOgNk9IAAGwXZ00AAAAAAAAAALD0mDABAAAAAGAavLMGAADziIwCADsTv98BzLn/A0fnzjZz4WIvAAAAAElFTkSuQmCC>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACMAAAAZCAYAAAC7OJeSAAACLklEQVR4Xr1WPUsdQRS9g1/YmcKYxmAREAwiIWptxCaE/ACx08pCBBMttEyZYBUI4g+wEJJGG3+BkCaFpgqpIkIKQQVBQfTcNx97d3ZmZ55PPXLe3rnnfu3uzCLRvUDhrzlEMrRTCS0Y5qEaw56qt4ySfgO+SaY45NRPQKYLe5DsMGEEOqcGiegRt8Vb8CvpYSY9rTmE3nXK4+n74BOqG6ZaUMKq9VElqGB0L9hm7BsEhIepIlCqSQQqfBN2+MkEkvJQl+g0Z6yQHqBMRV1eXHBZRVaACYrFFt+Q0pPx96LdVN/h7oY8DXtXS67BEX7/gs/AdyZ+VYsOM+AlOAQ+Rc4ZruNCnwJ/ks6Fptq1uxiGi/8C160D0m9c/rkIUov42QN7Cp973MPCd6700WVwB9aXhJ6ELSrxgopx/1BVZ5wggv1fxI3ZWssU2qA+5NsxNpLVhXD7YN0bppFpG38Qwn/hZz4XWql5bFtx0o+YSFo/8Z1UNHwlKr8GN7G+MtqGUzLBd77gO4H35spFt7TpumIjKm44ZtZrpONGRAy/pu1iaYyau2ZwkW3P10/6081g/YANcwQHwGNw1uiMHdJxncL3CRwV6wYSszROCJ8kPobX4EewT+gd4Dx4SnqIOeMjr/QEeEj6OH8GX0qxFMp2Zaq0IwM6Jz8zP7Il+F/SHDSf0QJss2TTZEAdosn8fKJiBhq5rRTIwUPXj0D+g38nZOdnB+bAFONLpa4K+B4Jt4GGW+LT3qHhAAAAAElFTkSuQmCC>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAYCAYAAADDLGwtAAAA+ElEQVR4XoVRsQ0CMQxMEA0dDQsgdmAFaOmooGEKKhZAYgQaVqCgZAUkaJgCIQQUz9lJHDv/L066d3y5OPbHuQivvhllLvCyVUZJW89aiK0DbsEJOAAvYK9WF9hBqnLqab3MeUAXfIFDVYGMla44Ap8QFkmIf6GSG6KX+qKT1JfWyfhNGguB5vfQkvRDtskV3LyJ0NfKyCdvWgCO4F2y1Au4V1f3wTe4iUMZ41Qy508ybchlQb2M8wZP++GdsJ90Nq5iMgNPLjxARvSeEa+Ic/Dh+H01pKJZNuQ1Y2lvgMxbxD8obb69QpkL7IH0Qm1lamgwlFNbi3c/p1YsdfjmfRIAAAAASUVORK5CYII=>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADsAAAAZCAYAAACPQVaOAAADmklEQVR4XrWYS6hOURTH1yFCuh4x8Chd6SoxkAwvuggDogxkLskrj8hMBhIiTFAGyECKZCAGIgMJUQrlGcljhBsyEOt/9t7fWXudvb+zz/H51brf2f+11j5n7dc5XaLaZN5PjAp3mTwhq86rDCgTT4l7LO0C2vlK/GFb5Cm10ikYH5AiIgk9bQITAigU002hYsssZxvmpZf70pxnG6hFn+pOOsUCtpNkil2sfJInbHu1aJnNdpxtDJl+VgpfD1u/uYwVFdMrqEpTfoz4bbax1Co22APE92yDtYNMMV+pSHzJdq9w5+xhmyiF4F18qkKq/CXusg2y1+1m9hrbKC1akHdMtBELTQNthhYbUrtQMF9c58WiF9XTNOsL4VbEVKE9sJrmN9sVLSbTqLyCHWQeSttIGcS8srq+n9uf+3251Y/mFDn9Hx+8E+Qzq0Uy+jMtMqvJ+OTqALFiN1NYz8EIw4mpH8q2gu2mDGDesb1lG8e2kEz8AS+CaBXbNjLLcQ3bd99NfWT2LnJxag733bl+TmkAB5YpLGsV6OyzDLT08pQGi8VeuM92lIpJf8jWL75pMFI32EY7gcqj2s32TbQfU2R026wsxMsDiGy0u9c8WGZ+3YCfdpGC6N53IyaZzM0B9voFtRK9IMy07HCLbeOE3MnWJXxBykXns7Fdq1QeWIBB+UTFCS/IhpCMFzeC+CNwZ0foRkDrk8gsKTd4GKQpwp8CcndrkYyOpUziyV+TXAWZV4A7uUtAvOwpfuHwf/EUgy4WeTP57y22n9Z31vNXg5zDWiSjYxs5llgNW0eRP3xPvrcDE4ikrVokc0gB+C9IBzPH6vgFu2x7VivCHCRXW+00kHNRi2R0bA/ZfiPaGnx3FxOhlvGlopkznswhhX0L/1Phw2mM9+FGoeEUx2cb9ooDeb2iHad4GOTgYPNEqz2313hb/GKbW7hLbCBZrGAE20EySxVTj8NlgvDjAFhn/R/Z1lL4u/UM2yMyr5ZDypfKCdIPWdS8icxs6tddiA9kvqHbE1jmtYn3EfdYMFvBGWlHoFf0cUSLwcja5H0k/KeBkm63lG29FpPJqIsP5uu+VL7y8GXZiiR0jPwdYvdtEzIM1PT//ph1MK/F6BP1ZeVPzQSyO/xnn1aTaTan6ZEuNJCxjPzTPQV8L7gvP/J6DdxAkLYHgzRONJTTmw15hCYdxHJieodo3H1Cog7R7doEOnBSwEUxtZ6c0V/DEr5DM/wn+QAAAABJRU5ErkJggg==>

[image9]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAAiCAYAAADiWIUQAAAEsElEQVR4Xu3dW+gtYxjH8XeTU8iZJIcLOZUilw6JQqKcQlyg9o242+1Sal9sRFIoF0raF8rhHhGFHPa+cr5ADrvccOVCCInn13rHeub5z1oz6zBrZtb6fupp3nlm/mve/8z81zz7nVlrpzQE22ICAABAKBIAAAAwq8Y1ZOMVgWk4kQAAADq3niXZev5WWBbODwAAAGAgKN4BAFgpLr0AAGA2VA8AgKjza0PnHQAAAAB6j6oZAIaB92sAwPq6y+KDmOzYHzHRkfss3opJAACwkTobGbjQ4o3c/tcv6NAnqR99OSpPDyhl+66zU2n9sWsBTMY7RNuetjg4Jh0tPyIm18y5edqHIkl01vehL49ZvGTxelwAAEAtarhGqi74n8aEOaY8W7l3l3278AqL7yyOjgs69GNMdOSjPK06fqv2pGtf6toDUHkeo2c4SgCw9YJ/YJiX52NiAt0SK26PLeowi8stdqRmBdtDMdGCi/P0+lK2GzpuRdS5JSaW7BrXvsi1q7wbEwBmRQkLbKLvw3wxcuPFouA1i7MsHrd4JSz7OMwvamdqVrDptlwTKj7fsTgvLnAus/jK4nCLPy2esLgyjQukX8arLuQUi18tzkjTn//63OIpixct9rv8l2nrsalyc0xM8HWq3zf3WuxLo5E0v+1v0uiZujofxgSAwaOCBFbgBYsLcnvSM0j+wlyMLil3fFhW5Kv4EaEYN7r1oqYjbCoe6/yVxrd2J/VT9Dze/Wm0zrV5umxXW3yb2yqSqkY2PfVB68zTlyYjbNo3hWnb0GupSFfh9qjFaeXFtfbGBACgMYrjDXadxSMx6ZyQqi/gk36mat1FaIQtPD/3v1j4+bjBrSfHWuzJbX04wvfzAYvb3LxouYqqpuL2ffzt1iv47fvlKqA1mveby52cyuvX0bGJffARaZRvT27HfaM3h3hLvOo1Jtq2dfs+dH4BAIAaKobetnh1StkeL9Aqbg4NuUJcd1Eq2FRsVXJ9rhth0zNuKnxkdxrd1ivck6oLtjb51/ftXXnqC7Zn0mLfcVY3wqbtV+0bnRsHpeXuG0bYAACYU90FOC6P854vhJZBBdtxMVmhrmA7O43rO/X/dItL8vzdqVyU3JTKBVMbfs7T99OoP3p+zIsF3SFuflZNCjbtG33QI+6b/an86V99IvRNNz+rJgWb+nBnbj/s2u+l9o8LAAC9dWtMBLFA0y20EjfSpVusy6CX1HZ9TFNXsIkejP8sjUbsfnJ5jbDd7uYftLjKzbdB/f0nt5+zOMkt02ia/867oribV13Bpg88aN9sT1v3jZxvcWRuq1g71S2bVZOC7XeLc3Jbx6Foa/Rx2V8dAwAomXK/DYPQZITn5ZhYIY0OzUsF2x0x2ZEvYqJDz+bpmWlcsC3qxJgAAFTZgMJpA37FSi3/3j/ERKBPMOqB+SFqMoK3Kk1HFFdFX2+i/8UAQKtafgcHAAAAAACYG+MWAAAAwEq1UIK38JLAZuGPCAAAzI9KAgAAAADmwD+mAAAAgN4acrk+5L4DACrx1j487phx+ABsDt7xAADgegjMjT8eAADWCpd2zI6zBgAAAAD6gX+foSXx1Irz9Wb/CQzbf81xzcAbvA7KAAAAAElFTkSuQmCC>

[image10]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAkAAAAaCAYAAABl03YlAAAA60lEQVR4Xm1Ruw3CQAy1Z0BCAjELBQNQ0jBCVmAONqBkAkpKhKCnR5RICFGGl7vz2WfnKZafn79JiIkpQ7zA6zbva72gYWFBqIzlsdmxnYKgaQ+HbQWDkN5UKkStYcqFPoV+pxxZ5Ein7TDoBb9Oa5k6uA/8UauZzrAF+A/+AOUK3sG+cuMydRNN4HrYKqlET4jvwmla/Ab2kNH1Ovc+d9i2JlxywIzzqnkObYV27HHfUFSFyIkvsH7QyklFbv0NdsqCO6b9kdzklcpNvrkNDWqxHGb0wF1N01wFS9ORYbmtGtlTJ4bGUbgqhH/ZNhTTDO2R3AAAAABJRU5ErkJggg==>

[image11]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA8AAAAZCAYAAADuWXTMAAABYElEQVR4Xo1ULU8EMRCdJoQ7jTmFAYHiQ+JJLiR4JBIJ/AcSEhKC4Q9g0PcDMKBAgMYgCT8AQcIhjtfOdDrtdru85F133puZdrqbI+qDK4WEzPJBI7cCV3aolAepSKykKWqeQ+OBepEaMyS5J2EIPF0srjYxYtUfQLMmv1wzjRjRlyi65rmLd3gfWEdI2sf6BS7A3TzNQHptgL/gjul+g8c5orHurVY6wSHxDpuqMO7BcxNvg6cmDnhEI19sMULvH6zTOGrPtM4XlsV7jrVxX1XEIu2smU+ix0FvwRf/oea9HL2R7hysK4n1NFC3KMxfO4ZzU/x+g5/gJXHhTHJXwAk4D6lckZAEfzPuWe7hJGXQGXXvhY5EXJMOyxJf+0bmS/TaMfHrU9yBr8SvZh3rA3gBLnnTHNEXr6LZAYfRsUPIc2cuBTvGz1PLwjJu4x/Z5oDFUWp/hlWk2kzU76hxB39D9C4ccuR02wAAAABJRU5ErkJggg==>

[image12]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAAiCAYAAADiWIUQAAACb0lEQVR4Xu3dPYvUQBgA4BHESn+ApQgKioj6FwQR7C1sBX+AqHiNhZZ2grYKIgiihYW9YGMrWAg2dqKFlY2IzrBZbphlb7OXj80mzwMvO3lnL+TyMfNuNseFAAAscaBMAADbyaQOAMAalI9ACwwlAH0w2gIAdE3FBT1z0QGwCeYfAABg2Fr61NLSalpcEQAA0Cq1OjBqEx3kJvprw9S59Bm0DzHulkkAAIbhZ4yjMW7HeFT0AcA+uFEFbTtVvT6OcSvvABgEc38P7GTYpGcx/u0RZ3ffGi5l7dJOmL2/DX/C4nbkwdYx0NMNZxYwJcuKoDz/uXq9k+XmLsY4XCYbOBHjW5msvCoTTI0pGhpwAcEWS4XZ1zKZye9uXdij733R10Ra340id75YXuVajO/Z8tWsDY2Y9QDoW3pGrbzL9qZY3kv5s7kHYfErzTyWeREW+8vlVa7EuFm1D8b4kfUBrVG+NmYXAjU9D7t3tFIBdy7rW2XdQqquvzEOVe2XeUeSjW9Pw/JtyPPXszb0JztZzcsAGzKiAXhe3KRCqa6TYXmx1NTpGF+q9ru8o3A8xv0yGR0J+9y2ER1TANpmkmDDUnHzqUyu8DrGkzLZorRN98pkTcdi/K7av/IOAIBaBligp4f6170jld5/pky26G1Yf5ty6b8zfCyTAL0b4KAPjN/lsPoPB2DGRAUAG/EwzL6qTM+PjZAKA2B6jP3tsB/pkvMLxsG1DAAAMAY+3QGQMy/M2RMwTK5NAAAAAABgwzr6uqKj1cKQOM0BAAAAAKjB7WQAAIZCbQrA5JkM2UbOW4AJMNgPm+NDP5xpw9DdcfgPB+9TLlTmAT0AAAAASUVORK5CYII=>

[image13]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAZCAYAAAAIcL+IAAAA1UlEQVR4XmNggAJGJBITMCIUoNJ4AEGFhKxEk0dXiKGAEEBSSEgnTnksQhCArgNVIYY2xsdAoQAg4z8QP0J4huE/I0QMDrKQJH4hiYMU/YeZrA1l8AFpkEQkksIiIN6PxAcrTAHir0AWD5LEIiC/HqEEArYC8WI0z/wEEkYQJoQUZ4C4xwSmEEgzAUkXqDxUFML8BKTsYRJAeiK6AhjNCaT+MkB8WQPksyFUYQFoboQ5DVMCJ0B1LKZCHCYiAKpWJFUYAlj5GEIIHnYD8AHsatFzIyMDAL3NF3DjwVVKAAAAAElFTkSuQmCC>