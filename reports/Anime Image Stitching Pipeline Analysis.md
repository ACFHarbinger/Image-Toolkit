# **High-Fidelity Panoramic Reconstruction of 2D Digital Animation: A Comprehensive Review of Computational Pipelines, Geometric Alignment, and High-Redundancy Mosaicking**

## **Introduction and Theoretical Foundations: 3D Photographic vs. 2D Stylized Domains**

The reconstruction of continuous panoramic backgrounds from sequential digital video frames represents a major challenge in computer vision, residing at the intersection of geometric image registration, deep feature representation, and photometric optimization. While image stitching in three-dimensional physical environments is a mature field with established algorithmic baselines, the visual topology of two-dimensional digital animation—commonly referred to as hand-drawn cel or digital anime art—presents unique challenges.1  
In standard photographic stitching, the spatial mapping between overlapping views is modeled using projective homography.1 This mathematical formulation assumes either a perfectly planar 3D scene or a camera undergoing pure rotation around its optical center.1 Under these assumptions, the spatial transformation is represented by a ![][image1] matrix operating in homogeneous coordinates, possessing eight degrees of freedom to account for translation, rotation, scaling, shearing, and perspective distortions 1:  
![][image2]  
Solving for this matrix requires establishing discrete spatial correspondences using handcrafted feature detectors such as the Scale-Invariant Feature Transform (SIFT) 2 or Oriented FAST and Rotated BRIEF (ORB) 1, and minimizing reprojection errors through robust estimators like Random Sample Consensus (RANSAC).1  
However, digital animation frames violate these foundational photographic assumptions. First, the visual structure of anime is characterized by flat, homogeneous color regions bounded by sharp, high-frequency line art.1 Handcrafted feature detectors, which rely on localized intensity gradients to construct scale-spaces, fail to extract stable keypoints in these textureless flat regions.1 Instead, keypoints cluster excessively along the high-contrast boundaries of moving foreground characters or localized high-frequency background assets, leaving vast swaths of the background devoid of features.1 Furthermore, because the extracted features along line art are frequently collinear, the resulting system of equations solved via Direct Linear Transformation (DLT) becomes mathematically ill-conditioned and rank-deficient.1 Under these conditions, minor sub-pixel matching errors introduce severe spatial distortions, localized tearing, or geometric bulging.1  
Second, animation layouts do not adhere to standard pinhole camera geometries. Virtual cameras in animation are often modeled as linear pushbroom sensors or Crossed-Slits (X-Slits) projection systems. Animators construct long background panoramas—known as panning shots—as flat, multi-perspective drawings where vanishing points shift non-linearly across the canvas. Forcing a global projective homography onto these non-planar, multi-perspective layouts overfits the low-dimensional structure of cel animation, destroying intended parallel lines and introducing unwanted perspective skewing.  
Furthermore, animators simulate depth using multi-plane parallax (often called "multiplaning" or "stacking"), where distinct two-dimensional background, midground, and foreground planes slide horizontally at varying translational velocities relative to the viewport.1 This layered movement violates the rigid-scene assumption of global homography.1 When a camera translates relative to these layers, a single affine or projective matrix cannot resolve the conflicting velocity fields, resulting in structural tearing and edge doubling in the overlapping regions.1  
To overcome these limitations, specialized reconstruction pipelines must replace the classical "perfect stitch" homography paradigm with a "scan stitch" model. This approach treats the panning sequence as a spatio-temporal volume ![][image3], extracting narrow dimensional strips or slits from the center of each consecutive frame and concatenating them along a optimized translation vector. This preserving of affine properties prevents perspective distortion, maintains collinearity, and enables the system to "look past" dynamic foreground occlusions.

## **Historical Evolution of Image Stitching: From Handcrafted Keypoints to SOTA Deep Architectures**

The historical trajectory of image registration can be conceptualized as a transition from handcrafted local descriptors to end-to-end learned dense neural matchers and non-rigid deformation fields. This evolution is summarized in the timeline below, mapping the progression of registration and alignment methodologies:

 \---\> \---\> \---\>  
    SIFT / SURF / ORB              SuperPoint / SuperGlue        LoFTR / EfficientLoFTR             APAP / CPW with LSD  
(Gradient scale-space)          (GNN Graph Matching)           (Spatio-Temporal Transformers)   (Energy minimization)

### **The Era of Handcrafted Features (1999–2017)**

The foundation of modern image stitching was established by David Lowe's introduction of SIFT, which constructed scale-spaces using Difference-of-Gaussians (DoG) and computed gradient-orientation histograms to achieve invariance to scale, rotation, and affine distortions.2 While highly robust in textured environments, SIFT’s reliance on local intensity variations made it fragile when processing digital cel art.1 Variations like Speeded-Up Robust Features (SURF) 1 and ORB 1 optimized processing speeds using box filters and binary intensity comparisons, but they still suffered from keypoint clustering and rank-deficiency when faced with flat anime backgrounds.1  
Geometric alignment during this era was dominated by global homography estimation and global gain compensation.1 Brown and Lowe proposed a multi-image stitching framework that optimized camera poses globally by minimizing reprojection errors of matched SIFT keypoints, using gain compensation to smooth exposure variations across overlapping boundaries.1 However, this global approach could not resolve spatial non-uniformity or multi-plane parallax, resulting in prominent blending seams and double-images.1

### **The Emergence of Learned Sparse Features (2018–2020)**

To resolve the limitations of handcrafted filters, deep learning models were introduced to learn interest points and descriptors directly from data.3 SuperPoint utilized a self-supervised MagicPoint architecture trained on synthetic shapes, followed by homographic adaptation on real images, to output spatially distributed keypoints and associated feature vectors.2 When paired with SuperGlue—a graph neural network that leverages self-attention and cross-attention layers to execute context-aware reasoning over keypoint graphs—learned sparse matchers achieved a major leap in outlier rejection.2  
However, these models still relied on an initial keypoint extraction step.3 In absolute flat-color zones common in animation, the network's keypoint detector would fail to fire, preventing the matching backend from establishing correspondences across these featureless regions.1

### **The Shift to Detector-Free Dense Matching (2021–Present)**

The current state-of-the-art is defined by detector-free, dense feature matching, pioneered by the Local Feature Transformer (LoFTR).1 LoFTR completely bypasses keypoint detection, establishing pixel-wise dense correspondences directly from raw image pairs.1 By passing downscaled convolutional feature maps through self- and cross-attention layers, LoFTR enables pixels in featureless regions to "attend" to distant high-contrast lines or boundaries within the same frame.1 This spatial context allows the model to assign unique, location-enriched descriptors to flat pixels, establishing accurate correspondences in texture-poor overlapping zones.1  
To mitigate the quadratic computational complexity of LoFTR's attention mechanism, contemporary research has introduced EfficientLoFTR.1 This architecture utilizes an aggregated linear attention mechanism and adaptive token selection, allowing real-time processing of high-resolution video streams while maintaining sub-pixel registration accuracy.1  
Parallel advances in spatial warping replaced rigid global homographies with non-rigid deformation fields.1 As-Projective-As-Possible (APAP) warping divides the image canvas into a uniform grid of mesh cells, calculating a localized homography for every individual vertex using a Moving DLT formulation.1 Content-Preserving Warps (CPW) further constrain mesh deformations by integrating Line Segment Detectors (LSD) to isolate linear structures across frames.1 The alignment is solved as an energy minimization problem that restricts mesh deformation to unstructured, flat regions while maintaining the collinearity of hand-drawn architectural elements.1

## **Detailed Section-by-Section Analysis of the Fourteen Pipeline Stages**

The computational pipeline engineered to reconstruct high-fidelity panoramic backgrounds from sequential digital animation frames must execute fourteen distinct stages.1 Each stage is detailed below, detailing its fundamental mechanics, mathematical formulations, and domain-specific challenges.

### **Stage 1: Loading and Dark-Border Trimming**

The pipeline initiates by ingesting raw, uncompressed sequential frames into a high-depth workspace.1 It immediately executes an automated spatial analysis to identify and crop static black borders (pillarboxes and letterboxes) commonly introduced during aspect ratio conversions, DVD/Blu-ray authoring, or television broadcasting.1  
Historically, this was achieved using global intensity thresholding, where any row or column with a median brightness below ![][image4] was flagged for deletion.1 However, this simple heuristic fails during dark scenes, nighttime sequences, or dramatic fades-to-black, resulting in erroneous image truncation.1  
To resolve this, modern pipelines calculate the temporal variance of the boundaries across the entire frame sequence. Static black bars exhibit zero temporal variance, whereas dark cinematic sequences retain low-frequency noise and temporal luminance changes. This stage must also detect and isolate static channel logos, subtitle bands, and timecode overlays, which remain fixed on-screen and would otherwise confound spatial registration algorithms.1

### **Stage 2: Width Normalization**

To ensure spatial and scale consistency before executing feature matching, frame dimensions are normalized to a standard target resolution.1 The scaling factor is calculated relative to a reference frame, typically the initial frame in the sequence (Frame 0).1  
This normalization is executed using Lanczos-4 interpolation, which applies a sinc windowing function to preserve sharp, high-contrast edge transitions along line art while minimizing aliasing.1 A major challenge arises if Frame 0 originates from an anamorphic stream or a video sequence with a non-standard aspect ratio.1 Scaling all subsequent frames to this faulty reference introduces non-linear aspect ratio distortions across the entire mosaic.1

### **Stage 3: Spatial Flat-Fielding via BaSiC**

Uneven camera exposure simulation, virtual lens vignetting, or digital encoding artifacts can introduce spatial luminance variations across sequential frames.4 The pipeline corrects these spatial anomalies using the BaSiC (Active-Labeling-based Photometric Correction) framework.1 BaSiC models the observed image intensity ![][image5] for frame ![][image6] as a function of a static spatial flat-field ![][image7] and a temporal baseline ![][image8] 1:  
![][image9]  
where ![][image10] represents the true, unshaded scene illumination.1  
The pipeline isolates and applies the spatial flat-fielding component to correct global shading while deliberately omitting the per-frame temporal baseline ![][image8].1 Bypassing this baseline correction is intended to preserve the natural, artistic brightness transitions designed by the animators.1 However, this choice introduces a severe downstream issue: during the temporal median rendering stage, the lack of frame-to-frame color and brightness harmonization yields blended composites where dimmed or brightened frames create uneven, blotchy horizontal gradients and exposure banding across the final background.1

### **Stage 4: Foreground Masking and Segmentation via BiRefNet**

To prevent moving foreground characters or objects from corrupting the background alignment and blending processes, the pipeline segments and masks out all dynamic elements.1 The pipeline deploys a single-frame Dichotomous Image Segmentation (DIS) model utilizing the Bilateral Reference Network (BiRefNet).1 BiRefNet features a Localization Module (LM) driven by a hierarchical Vision Transformer (ViT) backbone with Atrous Spatial Pyramid Pooling (ASPP) to capture global scene context, coupled with a Reconstruction Module (RM). The RM enforces sharp boundary details by combining a gradient-prior reference (which uses Sobel operators to align predicted boundaries with 1-pixel wide line-art contours) and a source-guided inward reference.  
To bridge the domain gap between photographic training sets and digital illustration, the model is fine-tuned on the ToonOut dataset, which elevates segmentation pixel accuracy from 95.3% to 99.5% on anime imagery.1 Once the binary character mask is generated, an aggressive spatial dilation (typically 16 pixels) is applied to create a "safety buffer" that captures fine boundary details, such as flyaway hair strands or motion blur.1 This safety dilation presents a severe trade-off: over-dilation in low-resolution frames or crowded scenes erodes too many background pixels, leaving the feature matching algorithms with insufficient static references to compute structural alignment.1

### **Stage 5: Pairwise Feature Matching via LoFTR and Fallbacks**

Spatial correspondences across adjacent frames are calculated within the non-masked background regions.1 The pipeline executes a multi-tier matching hierarchy designed to handle varying levels of texture and structure:

1. **Primary Matcher:** Kornia-based Local Feature Transformer (LoFTR).1 LoFTR is executed at a fixed internal resolution of ![][image11].1 This fixed resolution introduces a 27% aspect ratio distortion on standard 16:9 HD frames, which shifts the coordinate grid and degrades keypoint localization.1 The LoFTR model is typically initialized with outdoor weights (trained on MegaDepth), which represent an out-of-distribution domain for flat, stylized anime art, leading to matching failures on abstract backgrounds.1  
2. **Secondary Fallback:** Multi-strip normalized cross-correlation template matching.1 If LoFTR returns fewer than a critical threshold of matches, the pipeline extracts structural strips along the boundaries and slides them to establish local alignments.  
3. **Tertiary Fallback:** Phase Correlation based on the Fourier Shift Theorem.1 This fallback isolates translational offsets in frequency space, ignoring local intensity changes.

### **Stage 6: Global Affine Bundle Adjustment**

Once pairwise matching coordinates are established, they must be optimized globally to resolve cumulative drift errors across the frame sequence. The pipeline executes a global bundle adjustment.1 However, to maintain high computational performance and prevent geometric warping, the pipeline simplifies the optimization space.1 Instead of optimizing for full 8 DoF homographies or 6 DoF affine parameters, the system executes a translation-only (2 DoF) bundle adjustment solved via the SciPy Levenberg-Marquardt algorithm 1:  
![][image12]  
where ![][image13] and ![][image14] are the 2D translation vectors for frames ![][image6] and ![][image15], ![][image16] represents the set of overlapping frame pairs, and ![][image17] is the coordinate of the ![][image18]\-th matched feature in frame ![][image6].1 This rigid 2 DoF optimization prevents perspective distortions but fails to resolve rotational camera shake, zooming, or multi-plane parallax.1

### **Stage 7: Sub-Pixel Pyramid ECC Refinement**

To correct sub-pixel alignment errors that remain after global bundle adjustment, the translation vectors undergo refinement using the Enhanced Correlation Coefficient (ECC) maximization algorithm.1 ECC operates directly on image gradients using zero-mean normalized cross-correlation (ZNCC), making it robust to global illumination changes.1 The optimization is executed across a 4-level image pyramid using OpenCV’s findTransformECC.1 By starting at a low-resolution scale and propagating the refined translation vectors down to the original resolution, the algorithm achieves alignment precision up to ![][image19]\-th of a pixel without relying on sparse point features.1

### **Stage 8: Global Canvas Computation**

Using the refined pairwise and globally optimized translation vectors, the pipeline maps the relative coordinate system of each individual frame onto a single, unified global canvas.1 This step computes the absolute bounding box of the entire panoramic mosaic by identifying the global minimum and maximum spatial coordinates across all projected frames.1

### **Stage 9: Temporal Composite Rendering**

The overlapping aligned frames are synthesized into a single, continuous background layer using one of three rendering strategies:

* **Overmix Temporal Median:** Solves foreground occlusion by taking the median pixel value along the temporal axis at each spatial coordinate ![][image20].1 Assuming the foreground character is moving, the median operator effectively isolates and reconstructs the static background.8 This requires high-redundancy frame overlap (exceeding 95%) to function.1  
* **Laplacian Pyramid Blending:** Separates the aligned frames into bandpass frequency channels. Low frequencies are blended over wide spatial zones to eliminate lighting variations, while high-frequency bands are merged using narrow transitions to preserve sharp hand-drawn line art.1  
* **Poisson Blending:** Solves a Poisson partial differential equation to match gradient fields, ensuring ![][image21] spatial continuity across image boundaries.1

### **Stage 10: Foreground Layer Composition**

Once a clean background canvas is reconstructed, the pipeline restores the artistic narrative of the scene by compositing the foreground characters back onto the background.1 The system selects the "best single frame" (determined by character posture, lack of motion blur, or central positioning) and pastes its high-resolution, segmented foreground pixels over the synthesized background using alpha blending.1

### **Stage 11: Largest Inscribed Rectangular Cropping**

Because camera pans and localized warping produce irregular, non-rectangular boundaries along the margins of the global canvas, the final image must be cropped.9 The pipeline executes an optimization search to identify and crop the canvas to the largest inscribed non-black rectangle, outputting a clean, standard aspect-ratio panorama.1

## **Detailed Section-by-Section Analysis of the Remaining Pipeline Stages and Advanced Integration**

While the eleven core stages form the baseline stitching pipeline, completing a fully automated, high-fidelity reconstruction requires integrating three advanced pre-processing and post-optimization stages.1

Raw Video Stream \---\> \---\>  
                                                                                |  
                                                                                v  
                     \<---

### **Stage 12: Relational Shot Boundary Detection via OmniShotCut**

Before executing geometric registration, a continuous, compressed video stream must be parsed into semantically coherent, discrete shots.1 Standard shot cut detection algorithms rely on heuristic frame-differencing or localized 3D convolutional networks, which fail when processing animation.1 Anime is characterized by highly variable pacing and "sudden jumps" where characters shift abruptly without a formal camera cut.1  
To address this, the pipeline deploys the OmniShotCut framework.1 Unlike classical systems, OmniShotCut treats video parsing as a structured relational prediction problem.1 It features a spatio-temporal Transformer encoder with 3D positional embeddings to process frames, using a ResNet18 backbone to maintain spatial token density.1 A decoder uses twenty-four fixed, learnable shot query tokens that interact with the encoded frame features via cross-attention.1 This setup jointly estimates shot ranges alongside intra-shot and inter-shot continuity relations.1  
To bypass label noise from manual annotations, OmniShotCut is trained on the synthetic OmniShotCutBench dataset, which contains 300,000 synthetic videos and 11.9 million parameterized transitions across nine families and thirty subtypes.1  
The baseline model's range prediction head originally utilized standard Cross-Entropy, which assumes classes are orthogonal and ignores temporal ordinality.1 To correct this, the pipeline reformulates range prediction using a differentiable 1D Wasserstein distance (Earth Mover's Distance) computed over the cumulative distribution functions (CDFs) of the temporal probability simplex 1:  
![][image22]  
where ![][image23] and ![][image24] are the cumulative sum distributions of the predicted and ground-truth probability vectors.1 This ensures gradient magnitudes scale proportionally with temporal errors, accelerating convergence and stabilizing training.1

### **Stage 13: Edge-Aware Super-Resolution via APISR**

Animation source frames often exhibit destructive encoding artifacts, including color bleeding from chroma subsampling (![][image25]) and line-art destruction from block-based Discrete Cosine Transform (DCT) quantization.1 Standard super-resolution networks, trained on natural photographs, tend to hallucinate noisy, photorealistic textures in flat shaded regions.1  
To preserve the topological constraints of 2D animation, the pipeline integrates APISR (Anime Production-inspired Real-world Super-Resolution).1 APISR synthetically replicates multi-frame video compression artifacts within a spatial image dataset using a prediction-oriented compression degradation model.1 During training, uncropped high-resolution ground-truth images are subjected to single-frame compression techniques (such as JPEG, WebP, AVIF, and H.264/H.265 intra-prediction), forcing the network to learn to invert non-linear degradation space.1  
To prioritize the reconstruction of faint high-frequency boundaries, APISR generates a synthetic Pseudo-Ground Truth (Pseudo-GT) by isolating and enhancing edges.1 To resolve optimization instability caused by sharp, non-differentiable hard-thresholding edge blending masks, the pipeline implements a parameterized, temperature-controlled sigmoid function to keep the blending mask continuous and differentiable 1:  
![][image26]  
where ![][image27] represents a thermal scaling parameter that regulates boundary smoothness.1  
The model is optimized using a balanced twin perceptual loss:

1. A ResNet50 model pre-trained on the Danbooru anime dataset to capture domain-specific semantic topologies and maintain flat color regions.1  
2. A VGG network pre-trained on ImageNet to enforce structural coherence and edge alignment.1

Because these two pre-training domains are highly non-orthogonal, their linear combination results in contradictory gradient fields.1 The pipeline mathematically resolves this by projecting the VGG feature gradients onto the null space of the ResNet feature gradients, ensuring structural constraints do not destructively interfere with precise anime stylistic rendering 1:  
![][image28]

### **Stage 14: Iterative MAP Reconstruction and Quantization Reversal**

For sequences processed with high-redundancy video mosaicking (overlaps exceeding 95%), the pipeline reverses block-level DCT quantization damage by formulating restoration as a Maximum A Posteriori (MAP) estimation problem.1  
Video compression segments images into discrete ![][image29] macroblocks, applying the DCT and dividing coefficients by a quantization table.1 This rounding truncates high-frequency data, destroying sharp lines and causing ringing artifacts when averaged.1  
Using sub-pixel camera movement, the pipeline reverses quantization damage over time through an iterative process 1:

1. **Initial Baseline:** Computes a pixel-by-pixel average of all aligned frames to produce a noise-free but slightly blurred baseline.1  
2. **Iterative DCT Mapping:** For each ![][image29] block in a given compressed source frame, the pipeline extracts the equivalent ![][image29] area from its current *estimated* high-resolution image and applies a forward DCT to convert it into frequency space.1  
3. **Coefficient Replacement:** The pipeline mathematically quantizes the estimate's DCT coefficients.1 If they match the actual coefficients of the compressed source frame, the algorithm replaces the low-precision, truncated source coefficients with the unquantized, high-precision coefficients from the estimate.1  
4. **Iterative Reconstruction:** By compiling high-precision coefficients from hundreds of spatially offset macroblocks across the video pan, the pipeline reverses quantization damage to restore sharp line-art.1  
5. **Prior-Knowledge Injection:** To prevent the estimation from falling into noisy local minima, a learning-based CNN (*waifu2x*) denoises and upscales the initial estimate to enforce a structural prior.1 The pipeline then forces this cleaned prior to conform strictly to the actual encoded video data via the iterative DCT matching process, preventing the AI from hallucinating incorrect details.1

## **Technical Comparison of Image Stitching Methodologies**

The technical differences, operational advantages, and structural trade-offs of the three primary image stitching paradigms are detailed in the comparative table below:

| Technical Dimension | Simple Image Stitching (OpenCV default / Brown-Lowe) | Custom Complex Anime Pipeline (Rigid Masked Translation) | State-of-the-Art (SOTA) Methods (Non-Rigid Mesh Warps & Advanced Optimization) |
| :---- | :---- | :---- | :---- |
| **Geometric Transformation** | Global homography (![][image1] matrix with 8 DoF in homogeneous coordinates). | Rigid translation (2 DoF) or affine (6 DoF), preventing perspective skewing.1 | Localized non-rigid mesh warping (APAP/CPW) with localized homographies.1 |
| **Feature Extraction** | Handcrafted sparse detectors (SIFT/ORB) relying on local intensity gradients.1 | Multi-tier hierarchy: LoFTR dense matching, falling back to template and phase correlation.1 | Dense matchers (LoFTR/RoMa) coupled with Line Segment Detectors (LSD).1 |
| **Seam Finding** | Graph-cut seam optimization or simple linear/average blending.1 | Masked temporal median filtering; pixels containing characters are excluded from the stack.1 | Dynamic MRF graph-cut seam routing weighted by ![][image30] to hide seams along lines.1 |
| **Exposure Compensation** | Global scalar gain compensation (least-squares fitting of per-image gains).1 | Spatial flat-fielding via BaSiC (temporal baseline correction is bypassed).1 | Region-Stratified Reinhard Transfer (k-means clustering) and Poisson blending.1 |
| **Chroma & Compression Handling** | None; processes standard 8-bit RGB, which is susceptible to color banding.1 | Native 16-bit space with support for chroma sub-sampling and IVTC decimation.1 | Iterative Maximum A Posteriori (MAP) reconstruction of DCT quantization coefficients.1 |
| **Primary Advantages** | Fast processing; zero setup; widely available in standard computer vision libraries.1 | Completely eliminates character ghosting; mathematically stable against perspective warping.1 | Absorbs complex multi-plane parallax; preserves hand-drawn line art; seamless color transitions.1 |
| **Primary Failure Modes** | Severe perspective distortions; keypoint clustering; alignment failures on flat colors.1 | Cannot resolve rotational camera shake, zooming, or local perspective shifts.1 | High computational complexity; requires fine-tuning of energy weights.1 |

## **Detailed Analysis of Intermediate Mask Outputs (Images 1-5)**

High-redundancy video mosaicking must handle dynamic foreground occlusions to reconstruct clean background panoramas.1 The pipeline addresses this by generating a sequence of binary silhouette masks (such as a 5-frame sequence represented by Images 1-5) that isolate the movement of foreground characters.1 An analysis of these intermediate mask outputs reveals several critical structural issues and their corresponding algorithmic solutions:

### **Boundary Erosion of Fine Details**

Standard deep learning segmentation networks trained on natural photographic images (such as base BiRefNet or Mask R-CNN) suffer from domain-shift errors when processing stylized digital art.1 Because these networks do not comprehend the sharp line art and flat shading of character cels, they fail to locate the exact boundaries of fine structural elements.1  
This results in boundary erosion, where thin details—such as strands of hair, fingers, or handheld accessories—are misclassified as background.1 If these eroded regions are not masked out during the feature matching phase, the registration algorithms will attempt to align these moving hand-drawn details, causing localized warping.1 During the rendering phase, these unmasked details manifest as duplicate edges and ghosting artifacts.1  
To mitigate this, the pipeline fine-tunes the segmentation model on the ToonOut dataset, establishing anime-specific geometric priors and elevating boundary accuracy to 99.5%.1

### **Temporal Inconsistency and Jitter**

Because the binary masks (represented by Images 1-5) are generated on a frame-by-frame basis, minor fluctuations in the neural network's confidence scores produce high-frequency boundary variations across adjacent frames.1 This temporal inconsistency—manifesting as boundary jitter or "flicker" along the edges of the character's silhouette—means that the spatial margin of the mask shifts rapidly over time.1  
When these masks are applied during the blending phase, this boundary jitter produces noticeable edge artifacts and flickering halos around the composited foreground character.1 The pipeline resolves this by applying a temporal smoothing function (such as a Kalman filter or spatial-temporal Conditional Random Fields) over the sequence of masks, ensuring smooth boundary transitions across the temporal axis.1

### **Dilation Trade-Offs and Differentiable Sigmoid Masking**

To prevent unmasked character boundaries from corrupting the background, the pipeline applies a 16-pixel spatial dilation to the binary masks, creating a safety buffer.1 While effective, this dilation presents a spatial trade-off: in lower-resolution frames or crowded scenes, dilating the character's silhouette erodes a significant portion of the surrounding background.1 This deprives feature matching algorithms of stable static reference points, causing registration failures in tight spaces.1  
Furthermore, applying a hard binary threshold to these dilated masks creates non-differentiable transitions during spatial-temporal blending, causing sharp, artificial edge seams.1 The pipeline resolves this by replacing hard-thresholding masks with a parameterized, temperature-controlled sigmoid function:  
![][image31]  
where ![][image32] represents the signed distance field (SDF) from the character's boundary, and ![][image27] is a thermal parameter that regulates the transition width.1 This formulation keeps the blending mask continuous and differentiable, ensuring smooth spatial-temporal transitions.1

## **Technical Step-by-Step Guide to Setting Up a Semi-Automated Anime Frame Stitching Pipeline**

This step-by-step guide details the setup and execution of a high-fidelity, semi-automated anime frame stitching pipeline.1 The implementation integrates Python, PyTorch, Kornia, OpenCV, and FFmpeg to process compressed digital animation source files into high-resolution panoramic background mosaics.1

### **Step 1: System Pre-requisites and Environment Initialization**

The pipeline must run within a high-performance environment supporting CUDA acceleration.1 Execute the following bash sequence to set up the virtual environment and install the required dependencies:

Bash  
\# Initialize and activate Python virtual environment  
conda create \-n anime\_stitch python=3.10 \-y  
conda activate anime\_stitch

\# Install PyTorch with CUDA support (adjust CUDA version as required)  
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 \-c pytorch \-c nvidia \-y

\# Install OpenCV, SciPy, Kornia, PySide6, and helper libraries  
pip install opencv-python opencv-contrib-python-headless  
pip install scipy numpy kornia PySide6  
pip install onnxruntime-gpu

### **Step 2: High-Depth Video Frame Extraction and Inverse Telecine (IVTC)**

Digital anime sources frequently suffer from telecining (3:2 pulldown) and duplicate frames, which introduce interlacing artifacts and corrupt temporal registration.1 We bypass standard OS media decoders—which perform low-quality software chroma upsampling and 8-bit truncation—to extract pristine 16-bit frames directly from the YUV video stream 1:

Bash  
\# Extract high-fidelity 16-bit frames using FFmpeg  
\# Combines: fieldmatch (IVTC) \-\> decimate (removes duplicate frames) \-\> 16-bit output  
ffmpeg \-i input\_anime\_source.mkv \\  
  \-vf "fieldmatch=order=auto,decimate,mpdecimate" \\  
  \-pix\_fmt rgb48be \\  
  \-vsync vfr \\  
  frames\_16bit\_%05d.png

The FFmpeg filters operate as follows:

* fieldmatch performs field reconstruction to reverse the 3:2 pulldown, preventing interlaced "comb" artifacts from corrupting edge analysis.1  
* decimate removes the redundant 5th frame generated during telecine pulldown.1  
* mpdecimate dynamically drops identical frames, retaining only unique keyframes to optimize downstream processing.1  
* \-pix\_fmt rgb48be ensures that 10-bit (Hi10p) or high-depth sources are stored in a pristine 16-bit workspace, preventing color banding in flat shaded areas.1

### **Step 3: Complete Python Implementation of the Multi-Stage Alignment and Blending Core**

The script below implements the core pipeline, incorporating photometric normalization, deep dichotomous segmentation, mask-guided dense matching, global optimization, and temporal median blending 1:

Python  
import os  
import cv2  
import numpy as np  
import torch  
import torchvision.transforms as T  
import kornia as K  
from scipy.optimize import least\_squares

\# \==========================================  
\# STAGE 1 & 2: PHOTOMETRIC NORMALIZATION  
\# \==========================================  
def reverse\_broadcast\_dimming(frames, window\_size=5, threshold=0.10):  
    """  
    Detects drops in rolling peak luminance and scales brightness back to original levels.  
    """  
    corrected\_frames \=  
    peak\_luminances \= \[np.percentile(f, 99.5) for f in frames\]  
      
    for idx, frame in enumerate(frames):  
        start \= max(0, idx \- window\_size)  
        end \= min(len(frames), idx \+ window\_size)  
        local\_baseline \= np.max(peak\_luminances\[start:end\])  
          
        if peak\_luminances\[idx\] \< local\_baseline \* (1.0 \- threshold):  
            scale\_factor \= local\_baseline / (peak\_luminances\[idx\] \+ 1e-5)  
            scale\_factor \= min(scale\_factor, 1.5)  \# Cap scale factor  
            corrected\_frame \= np.clip(frame.astype(np.float32) \* scale\_factor, 0, 65535).astype(np.uint16)  
            corrected\_frames.append(corrected\_frame)  
        else:  
            corrected\_frames.append(frame)  
    return corrected\_frames

\# \==========================================  
\# STAGE 3: FOREGROUND MATTING (BIREFNET)  
\# \==========================================  
class ToonOutSegmenter:  
    def \_\_init\_\_(self, model\_path="birefnet\_toonout.pth"):  
        self.device \= torch.device("cuda" if torch.cuda.is\_available() else "cpu")  
        if os.path.exists(model\_path):  
            self.model \= torch.load(model\_path, map\_location=self.device)  
        else:  
            \# Fallback to a structural dummy or placeholder if model weights are loading dynamically  
            self.model \= None  
        if self.model:  
            self.model.eval()  
        self.transform \= T.Compose(, \[0.229, 0.224, 0.225\])  
        \])

    def generate\_mask(self, frame\_16bit, dilation\_size=16):  
        """  
        Generates a dilated binary foreground mask using the fine-tuned BiRefNet.  
        """  
        h, w, \_ \= frame\_16bit.shape  
        \# Downsample to 8-bit RGB for neural network inference  
        frame\_8bit \= (frame\_16bit // 256).astype(np.uint8)  
          
        if self.model is None:  
            \# Fallback: return a black mask (no foreground detected) if model is not loaded  
            return np.zeros((h, w), dtype=np.uint8)  
              
        input\_tensor \= self.transform(frame\_8bit).unsqueeze(0).to(self.device)  
          
        with torch.no\_grad():  
            output \= self.model(input\_tensor)  
            mask \= torch.sigmoid(output\[-1\]).squeeze().cpu().numpy()  
              
        binary\_mask \= (mask \> 0.5).astype(np.uint8) \* 255  
        binary\_mask\_resized \= cv2.resize(binary\_mask, (w, h), interpolation=cv2.INTER\_NEAREST)  
          
        \# Apply safety dilation to capture fine details  
        kernel \= cv2.getStructuringElement(cv2.MORPH\_ELLIPSE, (dilation\_size, dilation\_size))  
        dilated\_mask \= cv2.dilate(binary\_mask\_resized, kernel, iterations=1)  
        return dilated\_mask

\# \==========================================  
\# STAGE 4: MASK-GUIDED DENSE MATCHING (LOFTR)  
\# \==========================================  
class LoFTRMatcher:  
    def \_\_init\_\_(self):  
        self.device \= torch.device("cuda" if torch.cuda.is\_available() else "cpu")  
        self.loftr \= K.feature.LoFTR(pretrained="outdoor").to(self.device).eval()

    def match\_masked\_pair(self, frame1, frame2, mask1, mask2):  
        """  
        Computes dense LoFTR correspondences, filtering out points within the foreground masks.  
        """  
        h, w, \_ \= frame1.shape  
        img1\_gray \= cv2.cvtColor((frame1 // 256).astype(np.uint8), cv2.COLOR\_RGB2GRAY)  
        img2\_gray \= cv2.cvtColor((frame2 // 256).astype(np.uint8), cv2.COLOR\_RGB2GRAY)  
          
        t\_img1 \= K.image.to\_tensor(img1\_gray).float().to(self.device) / 255.0  
        t\_img2 \= K.image.to\_tensor(img2\_gray).float().to(self.device) / 255.0  
          
        input\_dict \= {"image0": t\_img1.unsqueeze(0), "image1": t\_img2.unsqueeze(0)}  
          
        with torch.no\_grad():  
            correspondences \= self.loftr(input\_dict)  
              
        pts0 \= correspondences\["keypoints0"\].cpu().numpy()  
        pts1 \= correspondences\["keypoints1"\].cpu().numpy()  
          
        valid\_indices \=  
        for i, (p0, p1) in enumerate(zip(pts0, pts1)):  
            x0, y0 \= int(p0), int(p0)  
            x1, y1 \= int(p1), int(p1)  
              
            if 0 \<= x0 \< w and 0 \<= y0 \< h and 0 \<= x1 \< w and 0 \<= y1 \< h:  
                \# Retain keypoint only if it is marked as background in both masks  
                if mask1\[y0, x0\] \== 0 and mask2\[y1, x1\] \== 0:  
                    valid\_indices.append(i)  
                      
        return pts0\[valid\_indices\], pts1\[valid\_indices\]

\# \==========================================  
\# STAGE 5 & 6: BUNDLE ADJUSTMENT & ECC  
\# \==========================================  
class PoseOptimizer:  
    def \_\_init\_\_(self, num\_frames):  
        self.num\_frames \= num\_frames

    def optimize\_translations(self, pairwise\_matches):  
        """  
        Minimizes global reprojection error using translation-only bundle adjustment.  
        """  
        init\_params \= np.zeros(self.num\_frames \* 2)  
          
        def residual\_function(params):  
            translations \= params.reshape((self.num\_frames, 2))  
            residuals \=  
            for (i, j), (pts\_i, pts\_j) in pairwise\_matches.items():  
                t\_i \= translations\[i\]  
                t\_j \= translations\[j\]  
                diff \= (pts\_j \- t\_j) \- (pts\_i \- t\_i)  
                residuals.extend(diff.ravel())  
            return np.array(residuals)  
              
        result \= least\_squares(residual\_function, init\_params, method="lm")  
        return result.x.reshape((self.num\_frames, 2))

    def refine\_ecc\_subpixel(self, frame\_ref, frame\_src, initial\_t):  
        """  
        Refines translation vectors using a pyramidal Enhanced Correlation Coefficient search.  
        """  
        ref\_gray \= cv2.cvtColor((frame\_ref // 256).astype(np.uint8), cv2.COLOR\_RGB2GRAY)  
        src\_gray \= cv2.cvtColor((frame\_src // 256).astype(np.uint8), cv2.COLOR\_RGB2GRAY)  
          
        warp\_matrix \= np.array(\[1.0, 0.0, initial\_t\],  
            \[0.0, 1.0, initial\_t\], dtype=np.float32)  
          
        criteria \= (cv2.TERM\_CRITERIA\_EPS | cv2.TERM\_CRITERIA\_COUNT, 50, 1e-5)  
          
        try:  
            \_, warp\_matrix \= cv2.findTransformECC(  
                src\_gray, ref\_gray, warp\_matrix,   
                cv2.MOTION\_TRANSLATION, criteria, None, 5  
            )  
            refined\_t \= \[warp\_matrix, warp\_matrix\]  
        except cv2.error:  
            \# Fallback to initial translation if optimization diverges  
            refined\_t \= initial\_t  
              
        return refined\_t

\# \==========================================  
\# STAGE 7: TEMPORAL RENDERING & COMPOSITION  
\# \==========================================  
class PanoramaRenderer:  
    def \_\_init\_\_(self, canvas\_shape, translations):  
        self.h\_canvas, self.w\_canvas \= canvas\_shape  
        self.translations \= translations

    def render\_median\_panorama(self, frames, masks):  
        """  
        Synthesizes the background canvas using a temporal median filter on unmasked pixels.  
        """  
        num\_frames \= len(frames)  
        temporal\_stack \= np.zeros((num\_frames, self.h\_canvas, self.w\_canvas, 3), dtype=np.float32)  
        temporal\_masks \= np.zeros((num\_frames, self.h\_canvas, self.w\_canvas), dtype=np.uint8)  
          
        for idx, (frame, mask) in enumerate(zip(frames, masks)):  
            t\_x, t\_y \= self.translations\[idx\]  
            T\_mat \= np.array(\[\[1.0, 0.0, t\_x\], \[0.0, 1.0, t\_y\]\], dtype=np.float32)  
              
            \# Warp frame and mask onto the global canvas space  
            warped\_frame \= cv2.warpAffine(frame, T\_mat, (self.w\_canvas, self.h\_canvas), flags=cv2.INTER\_LANCZOS4)  
            warped\_mask \= cv2.warpAffine(mask, T\_mat, (self.w\_canvas, self.h\_canvas), flags=cv2.INTER\_NEAREST)  
              
            temporal\_stack\[idx\] \= warped\_frame.astype(np.float32)  
            temporal\_masks\[idx\] \= warped\_mask  
              
        bg\_canvas \= np.zeros((self.h\_canvas, self.w\_canvas, 3), dtype=np.uint16)  
          
        for y in range(self.h\_canvas):  
            for x in range(self.w\_canvas):  
                \# Retrieve temporal values where the coordinate is classified as background  
                valid\_indices \= \[idx for idx in range(num\_frames) if temporal\_masks\[idx, y, x\] \== 0\]  
                  
                if valid\_indices:  
                    pixel\_values \= temporal\_stack\[valid\_indices, y, x\]  
                    bg\_canvas\[y, x\] \= np.median(pixel\_values, axis=0).astype(np.uint16)  
                else:  
                    bg\_canvas\[y, x\] \= 0  \# Inpainting placeholder  
                      
        return bg\_canvas

    def composite\_foreground(self, bg\_canvas, best\_frame, best\_mask, best\_idx):  
        """  
        Composites the foreground of the selected best single frame onto the background.  
        """  
        t\_x, t\_y \= self.translations\[best\_idx\]  
        T\_mat \= np.array(\[\[1.0, 0.0, t\_x\], \[0.0, 1.0, t\_y\]\], dtype=np.float32)  
          
        warped\_fg \= cv2.warpAffine(best\_frame, T\_mat, (self.w\_canvas, self.h\_canvas), flags=cv2.INTER\_LANCZOS4)  
        warped\_mask \= cv2.warpAffine(best\_mask, T\_mat, (self.w\_canvas, self.h\_canvas), flags=cv2.INTER\_NEAREST)  
          
        alpha \= warped\_mask.astype(np.float32) / 255.0  
        alpha\_3d \= np.repeat(alpha\[:, :, np.newaxis\], 3, axis=2)  
          
        final\_mosaic \= (warped\_fg.astype(np.float32) \* alpha\_3d \+   
                        bg\_canvas.astype(np.float32) \* (1.0 \- alpha\_3d))  
                          
        return np.clip(final\_mosaic, 0, 65535).astype(np.uint16)

### **Step 4: Human-in-the-Loop Interactivity**

While the pipeline is highly automated, extreme cases—such as long sequences of absolute flat color or camera zooms—can cause geometric registration to fail.1 Under these conditions, the system transitions to a semi-automated, human-in-the-loop control scheme.1  
An interactive PySide6 graphical user interface allows the operator to manually place anchor control points across overlapping image pairs, override erroneous automated correspondences, and paint custom seam lines using a digital brush.1 These manual inputs are integrated directly into the alignment optimization as hard boundary constraints, using Thin Plate Splines (TPS) or Moving Least Squares (MLS) warping to interpolate the deformation field smoothly between manual control points 1:

Python  
class HybridStitchPanel:  
    def \_\_init\_\_(self, frame\_ref, frame\_src):  
        self.frame\_ref \= frame\_ref  
        self.frame\_src \= frame\_src  
        self.manual\_control\_points \=  \# List of tuples: (pt\_ref, pt\_src)

    def add\_manual\_correspondence(self, pt\_ref, pt\_src):  
        """  
        Adds a human-annotated anchor point.  
        """  
        self.manual\_control\_points.append((pt\_ref, pt\_src))

    def compute\_tps\_warp(self):  
        """  
        Computes a Thin-Plate Spline deformation field regularized by human-in-the-loop control points.  
        """  
        if len(self.manual\_control\_points) \< 3:  
            \# TPS requires at least three non-collinear points  
            return None  
              
        pts\_ref \= np.array(\[p for p in self.manual\_control\_points\], dtype=np.float32)  
        pts\_src \= np.array(\[p for p in self.manual\_control\_points\], dtype=np.float32)  
          
        tps \= cv2.createThinPlateSplineShapeTransformer()  
        \# Format points as matching node arrays  
        matches \=  
          
        tps.estimateTransformation(  
            pts\_src.reshape(-1, 1, 2),   
            pts\_ref.reshape(-1, 1, 2),   
            matches  
        )  
        return tps

This hybrid design combines the speed of deep learning models with the precision of human validation, ensuring reliable panoramic reconstruction across challenging scenes.1

#### **Works cited**

1. Image Stitching Pipeline Optimization Research.md  
2. Robust Intraoral Image Stitching via Deep Feature Matching: Framework Development and Acquisition Parameter Optimization \- ResearchGate, accessed May 21, 2026, [https://www.researchgate.net/publication/399947944\_Robust\_Intraoral\_Image\_Stitching\_via\_Deep\_Feature\_Matching\_Framework\_Development\_and\_Acquisition\_Parameter\_Optimization](https://www.researchgate.net/publication/399947944_Robust_Intraoral_Image_Stitching_via_Deep_Feature_Matching_Framework_Development_and_Acquisition_Parameter_Optimization)  
3. UFM: Unified feature matching pre-training with multi-modal image assistants \- PMC \- NIH, accessed May 21, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC11957561/](https://pmc.ncbi.nlm.nih.gov/articles/PMC11957561/)  
4. IBEWMS: Individual Band Spectral Feature Enhancement-Based Waterfront Environment AAV Multispectral Image Stitching \- IEEE Xplore, accessed May 21, 2026, [https://ieeexplore.ieee.org/iel8/4609443/10766875/10747246.pdf](https://ieeexplore.ieee.org/iel8/4609443/10766875/10747246.pdf)  
5. Real-Time Panoramic Surveillance Video Stitching Method for Complex Industrial Environments \- PMC, accessed May 21, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC12788332/](https://pmc.ncbi.nlm.nih.gov/articles/PMC12788332/)  
6. Enhancing Feature Detection and Matching in Low-Pixel-Resolution Hyperspectral Images Using 3D Convolution-Based Siamese Networks \- PMC, accessed May 21, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC10534652/](https://pmc.ncbi.nlm.nih.gov/articles/PMC10534652/)  
7. spillerrec/Overmix: Automatic anime screenshot stitching in high quality \- GitHub, accessed May 21, 2026, [https://github.com/spillerrec/Overmix](https://github.com/spillerrec/Overmix)  
8. AI Guided Panoramic Image Reconstruction | CHNT, accessed May 21, 2026, [https://www.chnt.at/wp-content/uploads/AI-Guided-Panoramic-Image-Reconstruction.pdf](https://www.chnt.at/wp-content/uploads/AI-Guided-Panoramic-Image-Reconstruction.pdf)  
9. Generating High-Quality Panorama by View Synthesis Based on Optical Flow Estimation \- PMC, accessed May 21, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC8780851/](https://pmc.ncbi.nlm.nih.gov/articles/PMC8780851/)  
10. Stitching anime screenshots in overdrive \- Spillerrec's den, accessed May 21, 2026, [https://spillerrec.dk/2013/02/stitching-anime-screenshots-in-overdrive/](https://spillerrec.dk/2013/02/stitching-anime-screenshots-in-overdrive/)  
11. Moving Object Removal/ Motion Reconstruction in Stereo Panoramas, accessed May 21, 2026, [https://web.stanford.edu/class/ee368/Project\_Autumn\_1617/Reports/report\_yang\_wang\_wang.pdf](https://web.stanford.edu/class/ee368/Project_Autumn_1617/Reports/report_yang_wang_wang.pdf)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACgAAAAWCAYAAACyjt6wAAACmklEQVR4XpVUwatPQRQ+856y8OpXQhRhx0K9nchCz8pK2RAWkuzsbaWUjXqRlRSyUBZ62fAkHitE/gwrC0WSnu/MmTtzZs6Ze/nq+80533fm3Lkzc39EGSEPKVJBExsEZZc+NWqhtWPefx5ng9JObTHuh1Fbv0gH3YKuUdpOvULxm4rehIxSoLcqCwnHwc/gG/AZeBmcy35v1ojEWpSNVwvGThBdfhcRvEM8S94SuA7eSnkFt6EjVsc9LHYSqqqE4TaSdeSnlfUd/AEu6Ob/9pAB/1edUb2YPPwawj/gSVXyi2QXFwYhw3vu5BuoghTy0C13sEsdySIuOi/uZbEdSP0+cH9tVA/eCh4uaVng2OqcDcnf3gzBCsYP0Lj5FLjmBbi7NM0r2Iyfj+CB1ulB+8O6NK6AX0ju3tGpZmVu2IufV8QvVzAf+N8g0FIpSzRx2hy30EOgs8T3L9CF1vLnRZGPcZXkBOYxPgTP6CpB3UAy29QqLQIfMf0kuWNpxuSbHQFXUfEAyXnjjs6l3FrqVC3CnRh2qJxxj+Qrvq60PqRgA/gc/ATy/avnOU0cyYjbwd8ku7VF6fdJFnhTUreVIC0OwxMkFxEfRPwa4yxazdT4b9FpZ3c50B6ShXwDtyWNsRZEP5EqLUJ+Dt+5R+AN5R4K8nXrD6dBu5g+HqP0LibwETEuUVxceIpxrpR1G/Kdu0NVQQyPgWvgpkp10NMHbASXUfQV43uUvyVZJO9Mgm2RlFPgckllUEd1DrwqYtuj5K0TkcVQ4nbsz7SGVWp4vnSqHb87w1MbrUrVjnhTI1wjiaG23VIfpUGF9Pm18oD85tX0rNp+jKwV05TVgrHJ1zz4dXrRFspwC12xQehXmHvf7MSQmbKMvsP4C7UXPHPvboL2AAAAAElFTkSuQmCC>

[image2]: <data:image/png;base64,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>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFEAAAAaCAYAAADPELCZAAAFPElEQVR4Xs2YeehmYxTHz0WayTbZY2QZwySylCEkQ1lqJDJJlgZZokFMIomhLFPjD0tZhiZrdiFjCI0iiWSdTGlkLEWRfwhpfL/3PPfe8yzn3vd9f6Z86vzue7/nPOc597nPc+9zfyJ9VKlg6XUOuAvOgjQ5XrLKeLyYCSinKqsTU6cLOW3qUbopNPs/YC/Jod874F4Cm5+KfY02yuwwlPPbWRlxDezsVGxxGrWMMLpKFtMKp8LuNY4cv239O3PXlNWWAbdlhNBNYG/D5vEkrm6qDGeYA/sKNm04dCps3OyBWejmBxy3Sh0erOpl2G+wDTjbgOMa2OFJvQ/VfrX1aHZG5BV5GnZre1a3DQnGvW4v3tMnok12Omxn42h4CbZ4zC6rU0QHaHl68eHAaf4x7GQ9jZiBmN9x3C2WveU5FWxGL39ZjaljDha9Zg5kyvmw72Gbp460BkuTcGWkdiO5CH9vsZLhQtgnqUjy0Jwuxov29ClzHexv2HapA+wtOh7Hpg7iVbS1aKM1hRBO97dgm6WOwINo8VQqTkLWc8ZwRJFyM06Y91PRsA52dSoO8SPsT/SYdvkIbF+vEvAhbFkqBjjwd8A+EJ2t3EKcA3sRtgK2Txs5DB85z8NeFT6zu1WyLf5+plpKG9MwHb/fwHF1pZPmSxjPr28jOlYh5h7/sknufE808U5Gm4+wq8x5IGr8k5SLIA/Ajg+/T4D9IXpTOHjfwpZ2mfKClFrHTZQXgsA6n2zdImeJ1r2Xnnp5Io4TbcOaIkxrri7bT0tfD0+IJp4bgrYJWtwmz8A3+2WpCGYj9E5zfpFo/gNhB8Aeh+1u/H3wJh2JzmeJ5riWYihlBewb/TkyS6RedbJl6jBwAnCWjgW3KCzwtHDOAdij9fpwJi7KV04Gb8jXqVjT0yihqXGmacQZzdzjwGf86lRMuE80LqG/2ItFC7wcdgTsgthtsYkq7iu95dzABtzALm9OBmrx+FTi2bG/aM3cPRQodrKF6Cy8uexu4VJuHiGjUGfjs4sF3QW7LXL3Ur2LP0tTVfStfr/ohR4mzF3JQnNhnOnhOUaqOVV5H9owTbQ+bk0arhD9QDjIaJuKfv/u0CrxYPE5yDbzwvmCqngTKr69ORZjsWcoaC2Sbh95+u/Yw7BnUxGNbhJ9kcwVff4x94nBeZToC8bCzS1jDkn0Bm74v4PdGM5nCNtU8jN9psRmRT3XSRFcYfTvKDr4HKzpUYSyFnZJpJTGIdFY5F9SeGOV6NpW54ku1YSKLw9+PnEJLqv04jhr+QnJRwb7s3Dbwf4vTXTL0aJLjBf+Ouwf2DOtV4vijaK+vtVj+ML8CPY57E0Yt0gpXEUcaK4gyUaqjB/ke6Rxckmyw7kD0T5dswXiPYsr2UXirwsOKPvlTSzRfX0VyipINUHnnvQLL8bFzCyjpmcl6ohVsLsLeoGgx4cGbtpLG3DOFnyfV68ZjTNynZSXIuMfTcWMrMRWeAx2pXGMRpYvkA1ufbDR9W++PH4Rffj7eJ0ou8JecWK4P+R37rnh/EzYr7BDnfhl0I9JxRGZLfoF5FxLucMJKE6jxaKfeC3l7sqq6HNypu+uv5y4H3xHdPth3uwR3EDfkIo+0X+D+JxeCWG/TnKI6vSLlsKMKxDF3I4/JxlhDLz8lvjfX8MtQvxwYBPD7dPCSA+U82RCR48rMFBcwZmFZsKE/Fd5xmWcfm3sOO0GyZIVBn2UGE8Iv72YTLf0OhN3dzLQymPCZh6FMfgfMkFlWZNMGGDc+Anp7aZwd7L4TPCxof8C4T26nGXizJcAAAAASUVORK5CYII=>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACYAAAAZCAYAAABdEVzWAAADnUlEQVR4XqVWWahOURRe+7rGruGaLmXohqJE5ieZbnhREkW6lJuERMKL6VEyZErKC675AUVdId0yJAp5oFDKUIooQp6ub+2199nr7LP/oXz1/Xuvtb619zp7OOcnymBCN0IcydnWEI/vxvocVLCszoIVlVXlUS6/YkwLCuKCo0q41fLp0k5G5zLaHWB/F4lRBx4HO8WBABlsBvgY/OnaFqXw0zOb8dsGPoTBkw/Pa2gS+BLGMLQL4f2AdhFaV4Cpg24xOk/BTeLzyD8dgwd7Dc4Eh4AXwQ5wS7SS68Dn4EDn3wV+FpthfWfAw2Jb3CGbZ1rRXgEfQXaJ5MGk2DKbdRucp+yu4Dtk/EY7wOU1gH/gW6IGqkGfV2Sr8r0Cd9qe+PajMy2LCs6D44IZVyZ2Dcn2vQF7q+gJsAOSFpfGW8urqAa04BW5qewX4G5lHyB75jK0YN49yk4Dk9aCX0gmHckOKcQcZB/6G5z0mNMM9YkOvD38YN2cm7fsUBYlukXhgQeBT8DuIcw5PFi8aoLx4GzuKAkPyIXMEdNcZdvI4Hocfx5HOJu3DceA+pHNNSe9EFe3FXlNmV1AVJw1vU/aRvAveF9FpFDjCgs4Z/1EY8S08qVgu5FVtitJcutPB0nVyKlxs8x7khvqcYOkAFWYzTmLlv2jgr+AWkjvUnin9UTOPpLVnlBtncvAb+DYzCNLymeHCxic+QUXXGG8dQp6OrMZP83WJweqHVwFNsC4h7ZeiSm8rQPwPjP8mpiSebzG2APNBTTK+BmuOT/f7hQaSS4IuawmTMyXxetRMK11/QA1Ad+2t7CnBxfNIn57i2glSQETozPC5/BBzqMA6XVSXwdgO7wflc07c1TZpKviA8qfId5GDQxCC1y/HvofaFdYS3K7gF/BjU6jQhbLQd5GjW3gJ2VzYXxJHPRTGzoF8zvJF6Cd5O3NE/IKjQ4y/vapTwnRavAZhZvnYAfvA7ZRps0mnI/ur+C3D7reBzV6kRRQpLEtr4qCmYsfvlF8GY6AffPhrMfbw9/gGJ1JHm4N2IPk8Ksx8udEoWTAwkZzkqR+Krg3dirwPw+cPcOrzRcuPYoHh1kgIt9LpRR9kYe3lv8IlEReH6ziyA6hqISnZFY1+I/kbPJKY1SKU7QGKX3Kl0ZxlSqjOKnxb+3Yn/2WHjvxwo/lKUUeJRUlA4lQspKqEZ616E0ZaSQfvIo8i2p1GXyCToxWISXJeYoBi38f8YbA2eUXnwAAAABJRU5ErkJggg==>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAD8AAAAaCAYAAAAAPoRaAAAEZklEQVR4Xt1XWchWVRTdxzRzKPGhFMH4RXvQFIUwSFJUNCTDBBvE6sECh8aXhEQcSBEVQzAiHyTRFMmJkmyklyIo8UHEB3NAEMIhQV9UTMLWuvt89zvjvffzFx9csL577tr77DPdu+/+RDIwoXBPcBdGdUNUhjN5e06/v9Fk1WmfXuA+GIeGhjuDHSQ9ltV9I+6exc/nrhAiIcVo5OTjM3C2L5lMnMTCIsdoYUkk9NXgMldI+CiyBgcNfOaBB5o4eui2fyQQPcET4IS02UFgfx48Cv4H3rbXI+BLrpMHIz3w+zfizGgJ9ajxqTFHiPzNEvx8Y9vOJfck+vhJdPFjeON2SHSeBZ6WpKlT5ELk9CyGi85/dGioi9QHvA6nU6GhhB/hS/BTTwmRG7GJnmsnYA+3hbPgqrBTHMIq9jJNdNc2tcwu4s7yF/huKCoS3gWaPX5NUBFnO/h1Z2MZWSu6+BdaQhqFPkDU90XfVuIZ8GfwT/j/guvT4BfgLnCp61gN8wh+tojG+oSC1dn4QPQTW3pbMOMfC8U6/A7+C/YLDQmMFV38pNAgmi/4SvS38/oVvCLaZ51ov/7+pBNtvWwT3ciZErzLRjM7N7QU7A+fxvPlXQMMFA3OU/JhUEDoxrgYD71MjIpyqM3g4454Dtxj7zeAC2w7npwvsHg6aCUu8h+wr/UZITrft9Ts4Q3wFsivUR2KaHNEgy1vj1+2HpP4k9c6eV4TKN+3J8HbaM/3zJ2BB3Md1ApOA3PRHJ/xQ7wmavMWH220A1Zp7DClLVW5C0tZ+JvUY+9isWjcLk+tDO2b0X5V9Cmb7Mi7wYvOvYu3wauh2EY8+BnwJtg70D+EL4uGqcVdux/zAiekybHQS+Pr4Me2fRA85QzXJfHX5DlJvz4trAGviVZwND8g+grsVXOU1ZlQWbA1wjDRhTCjOjAT8POUaPKa79sKnIUPM64Lbh6rw69EF8QE+pu1cfI7RWO2MFJP1VwQfcdTWASfG7g+VNwZ+Uj0VXrf82rvwFYpvirRJnqHxLL0D5CBuXhmSG7Ay9Z1qNEBL4OPWs0FkpDhYkKsB38Aj4u+Rt8XNLIR1zHBlJhPeIrcpKgqs+CmMFF+Bx4WnTPnO67lEMTkZ45lbqjXw+2A9itSFAwyCO0HHRPBp+GShCfW8YgFNqPbE6EI8BEfFWg/giclPRLrgluwDE6bO4DhPzbN9DxNlr8uONAFu0F3AG9yh9wbBxyXpzzR3o/Xe/Ne28XDQnB/KKZRvzn8CvAdmhsaLN5BiG+1aRNPfcwQ/IO0IhRtnG1SVInysGiS5WO/o7T6YE7hI88aoBpu7/pJZ4097NMxPTR0AGZzzeQxukQLHOYNbgILpGC6ZWsl+KYruT6ZFWTkFNKufB342RkSGjzkdrt+55uAVWhR6kahG6G5Z/dRs2D3xFJqs7aLQG/o5qPSWGu++7g3A3ZnlHzftCWtViF99rZVXDqP6cAPH4WKhBxyjr5euZgEcpac/j8GLJ7QzqZF2AAAAABJRU5ErkJggg==>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAcAAAAaCAYAAAB7GkaWAAAA6UlEQVR4Xl2RLQ4CQQyFmQTJETAIEgyWhHAHAgaH4xYke4Q9BAKJx6CxKBSaIyCXb6c/09nutn3TeX2d3RmNekv5LZYXfVAgUFiFGFtS2UkFS2eQsli1Oq3WlqY93C95FyjixCPgBWFRSpUPTefmWILhdAI8AA/wKoikOYWbrp74NUqcSRtmz8gd+RQm+7yG9MMnfkhljfEPfgl8P9yB0IHW/NMp68Z3sJb0FrXUEpcuiy9Idz73im+9mgmDGfbIhmbnVGRF4YKtFopZwe5UZwinavHyQKovWWeUCyTBOq+MtQ5jGdNaFf8BuLoTQ9wgCCIAAAAASUVORK5CYII=>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAD4AAAAaCAYAAADv/O9kAAAEkElEQVR4XsVYW4hWVRj9toUWpYyWIBUko6JTFEkPQUQ3AsMeTBAD8WEUxYSUqDAKfDAoCLpRUSEpiFZjGuFUDqKWpWgXrIeohyh86IpGFyF6kLC19nfO+b+9z97nP/8/ggvW/Pus77IvZ9/OiJRwwU9vYFBToLe5Rh819dmIjH9GVgQVZpGxZ/uSVrvChnVNYRyqYhzEZ1dT+0CqZf530DnZbYxZ9NuIFnEbwOWxWKI5vrA2O9UwCfwEUTNDOYU4c/ysSKsR6k4TwI/AO2JDiXqIM1Jgrbt6hPJr4IOBQodMaG/oOcks8BdwcimkMqS0ErfBfAS/X4DHwLfBqeAb4BQzUPPAf7x2nqBNCboyCj5ihZZwj+LPV+CNRrwOuX/A76dGI54Bt0SagTaoaYTPBcr8xe9K8GeUJ5b2NrgTPAsOJRr7OlI/G2k/gUsjLUIik0fb5VA48af+dgsE2mzRPrAvafcEuF4ZVI1WFefkBZTvKh/xfLWo7/WVVpkyTyZZjLpi0WxN4AT4sC9xfJvCC9vzop3hAFwjulOGHh0sFvUdSNiIYdH9gctmO3gTuBMcAe/puDXB570WfAs8KJrT1sZ80cbqsQ98OVBS42/AzeqkaIfIP8ExeN4deGnoOvC/UK8wDD4OXgBeLD6X+xK8DOWPRQekDRh/WLixOnka8b8a21WibVxhtBIcEA5WT+AOfS/4BHgcFZ5FN0+jzKltgankfou0EqOcYH54nB9MNpADxUHgG+ep0fFOvQLFreBjoh7fgR8Y20qneecYTYpkm8H9oZ5H0TEGVi3hVH9JtALulraR7MjJdKMDca1o/GDSVTpXypwd4IxjjmXGsA20M8CCS/VDK9RzqzLgwtG0uEW00vsifTliz0SaJKp4U/Rt1RB3uBZZKs6v17/BiwoDXwg67Xi/SIHT/F0t1rNaLIH981jUGPcK/nwrnUpLLBQdkOqWVOBC8ElhTj0dfpfwrOcyWtF5dFzHvGNP72gRnN8X9hplvui+sd5oFmPgi7FYwYzFq+Bf4KpKcf4Ovkl0HfNsjDEo2nE2wqK8CzwA3l+Unyps7Bx3XDtYa4Q+Tt4phfB7ypd5YzxghPdF895QaDE4w1h3gfxb51FxhegXDo8eJsaHhzwnutPncEK04RbcHEec7t7sJM/+o+Au8QMp3NktuH55OvwY6RZXgjvQ/vdEc30PnhJOedOnojhDdFB4fHZDfkS6YCu4Jxb7BKdn1RTToktEZ5d9/kO0boV3riIWgd9UtnMOredmFM44nS1GTiFvAaaJn2mlT+DLN/yv6JlOPCQ6Q+ZbL1PeIelLTW+ImxsOrgfPZX7YJBHHZ8BvgNtZCPz1gR9HPJ6IIdHNcnXxHINn+tdS34grNLaHxqRDUpTLwc9E12E/uBTc6EvpV7hAdDbwQnJIyo+POrjeuVx41c61NQ/1z0RlZGCu02tiGq4ptAFdgiIzb3jDodQC6TrSamv0E95PTFeYpLX8TbYKeUuA3BsuxL7/75kM02xJk+T1CDm3nN4FLQczbxsnWiXOOGXkCuO1hxjvILSP/h8+hZ6icFbcigAAAABJRU5ErkJggg==>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEUAAAAaCAYAAADhVZELAAAEyElEQVR4Xr2YW8hmUxjHnzXODC4mBkVTDpmYRibKMRQpwsUkOVwgZAgX5mLI2YVBFIkLjYZx4XyIyEQNEW5Ics5Xzg3hiiKN/389a797rfWstQ/v+8386v/tvZ/nWc9ea+11ej+RqXG5YULsMVHGMILOxMOoFavZq5QLpFb/VA4MdDqLmD4wLxmfc94Y8uqOmB2gZ6H9W1NH9IRaTLDX3DFtzPHQw8MKSU+Y+TJDMPEPQefkxm1CWpU7oBsL9m3O+dDzuTGvVftUr23Z46r2AttDX0DH5o4+joY2Qj9BW6DP8AI+N/ouXDsSTyq0APoRT6cbT0LcsHBvAo2hl7hElH81/rzUehpCRBNovpJenhDtlH0nbuVA6G/E/I7ARbGj0JizoG+MNWDeOwLzriEpNIb1Z7sOb00RxpAyB32ot2aIfiCa+KjUbGDHPpgbZyetTU87pBDBtt2aG/tgL7LR9+QOsMKp73Nou9yZ8SV0dW6cCdO+sfgE66EXM0eBdCheJ9rwUyLrjtBlcG7GdRN0SE8N9xTNcXbuCBwjujZx1L0pupatg56E1tj5EWNG7hroBegZaK/IfoLoh9k5shHuQJ9ktl5ehbY47hpO7sP9TdBj0B/QbUlkneWinXJi7gDLRKfWwtC6t0Vzs8xdouUW1jsl4RJoNUJ3Fy23KvI9An0bPTdw9P7MmwFv8F9gV+FCWh5eJ0H/Qo9ndh6M3s1sXG9YSXZA/vYHoAPCPT3c0Z4OMXdDlwffEDg6doEuFn1fvCvOIef6ycvby0Wi7eDuGCh1T2s7TTQ5p1CJ90X9h0a2vZFgZZvC34WR4nhNPSmHieZjozyFGEkbVox4R3SdazhYNO+VhfgLgm+B8VRYK1qg0hjHYUf/QandwCM9OyWaPsVoVNrnW5LZPXGJYmm1LhbNwWnewGlk2hGg78/c2MV7EuZbgQshrjVcIBuuF38YcvGiTHYTrdSZmZ0wz+3h/mXo69blluDP/e2zh6NXp2GZZnQfF9n4W+tXSabIBC7MH+fGGvsJkzu/A8TwB9210F+iuwXjCOfvCvGLppsM/4g50XIB/1V3gv6DnhJt6D+iQ5/wGL5BNKeE+KWiDf5FtB4t7dBZinvG6Idxfo3jO7jeGFDsUdFdrpMjRdcKVpCd8gOuG8OIoL6C3hAd6vHZhFOE291vkm6FDdxiNxSGPafo69Cn0MnQa0H3osrRiPAlsV75L866+VNoZSJdKnp83wS9JdqR1yQRAafbMY/7W41zRXeqxY5nmbi+zi+em13+haeDOxYXz4zJaOI5qoHnEHYKj/Q5e4juPPvkjnnD6VlmJW7XOt0a1aqwAhz27LjY3kGIMaGOZ6cSZ4h2wA18cHqk+F64xUdE6a6Anmsfp6ZWUQ//V8I5el7uCFwFvZJYynm64A/Lm3NjgIc3dvwR4ZkHto+g5MdqgGsWp47fOTsZX8dRcPXn/1NOTc2j3nqnaINKcE3jbsUpzB+wPPxxhCaEt90i2onB0PmxG7q9CYND/SmZ04o7QbNrdTIk9ZA2ZXbuSOuMdRyFwgWTJ7bXYoYwS1nDLMmmKGuKGMPWIO35wd+h0zkT85y5ls7ba84eTDFjmJ5x9aoH1j3S4+x1G2qjxuQxhjr/Axa7uWqhUEUUAAAAAElFTkSuQmCC>

[image9]: <data:image/png;base64,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>

[image10]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEMAAAAaCAYAAADsS+FMAAAExElEQVR4XsWYW8hmUxjHn8U4M43zKXwx5XyOMlFjbogr5VTGxZgyzpRzEuECkSIhw4xTzjKUIbkZZxcSkriYQs7FDco0jf9/PWu/e+1nPWvv/b0mfvX/9lrP86zj3uvwfiIdgpOqE/KoMQUqTFdUS1XLVh1TMVSb43dMOf3ufu94xtQzJmbjsi/0QpMZ1/y4qJaB+CDH4+8DTaZ51ku5nmR0faPYAloDzTCTVzNVldVCVUfOrdAN1linnTSXirmPB1HqCmvc2Hj9UlvHMwf6ElqQG93CXcICBH2I5zpkNkCfQW9C76Ds98mWFHaPJSZlJxwA/QHNtY7xdGt12ujHFghyNf6u6nvnE1vHqRlOAAe9V+5KnCE62E0ag6n8LuiRrqmG162cIX9GyKOL1H6i4zlk4mgYaGJr6E/ofetI8LP7WJPuG/wOOrPjaCgaLgzTMVhNDFgL3dy1D3OS6DLIN509oetSehvo4cwXSf3ZB9oQghzWcfYwOI4pqJwXj0EvM9F43SjDHaKf1FEpj7HJQ3he3Ia0mApPEy07r/Aox4kuQexL8hZ0LPQo9BR0fRbnEPIq54a4Sce67lbnhMuFR3rRfHy5n1prgSn3nnBAId8sow7uRNlSyqXQevW0/pQ6FKkn8Nw2mdfA8Rueh0O3B22j8bW4zcgK0Yk9Vcq9gCcHJ1hM4UugH3JDgWlre2gdbK9mNk4C9wFD4IXmXWO8EvrR2BruhfZOaTb7DfRcyt8JnZ/SQ2wGvZLSHPQvovscmS86OUtTPudciKfkZOMvMJPRfObXZLb9oZVZvimzC3R6bhf9Mn42Ng9OMNtZ4r5411jAF8eNPt4wU5Gl6Ys2X3HkHNE265NhuE+0AD9BibuFfro7tiG9LBadfaU+qAtF25lhhmH10CpnidaxMLM9jZp+yvKKVn4R9HvX4ZB15AvRAnO6nSu6ehW0ClpkPKeIdnC7rjnCibolpgI+8yBfZ74Z6J42GzYVjd+5tRXcJnrf4VFPWAZLJjxfTm9Mc4P+JDP2cqDoQJr1WIPX2qMhboZLjI8/zljHkcbO3yrroWclbqTyN/R26jQH86RonQ3LROt5MebiWIoXcgH0F7RlyvPoZ5nLJhGRSbnlQU+tDrbWRaJHFGeNlVF8ayuzGMmK8VbKDvwq5s2liLXQMtsInDyyX4c+h06EVifxxsoJikHpcXLQyfu2NRUd50bKjfc16CPoA9G+H5EHtQQeq7yWG7M1zB7eMHmB2RV1bW583OG5hFxm2fbqPD5Lc0kc1GYjb0BfiW1Cc7yXcC/bzdgNrnGQlySeJIFveyvj4zJiw3vE3Czrn4QH2QH7N5eiR3MxPCHlj0l5nmYeXHa65KalZxz3w7ccz7M1W0Q+A11rjWVYL7xZLrTGxArRWyw3av484DJ5XPwWuCdxiczvuIMfHCkdpaVhhGcn0c7yN41DvYYEj/MbrTFjRnQ5chnxXw68sHVH2nITdF5uaOj2wvbJ5itUfghZeFnj6fGvGdWaA8rxlpyu5hX0LuXTunqCIp7fs1m8GM9m0Rg30jUmBnx97i4jI/vCGl9fzP9N+aXbfIceZ8VVMSuZszcu4kV4tv+Ucv6IZ5stfh2+1cNG2nxByEfTRv8DO8StN7KLo54AAAAASUVORK5CYII=>

[image11]: <data:image/png;base64,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>

[image12]: <data:image/png;base64,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>

[image13]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA0AAAAbCAYAAACnZAX6AAABd0lEQVR4Xp1UvS6EURC9N5GlUCsIJa1EdDqJTiFeQCFR6jRaim0kVN6B6EWi2Oj91BKJN6BbDefOnZl75vuswmzm3jNnzvzs7rebkliul1mOjOBcGT1ZwQnNSdRaZMdSp0HQ9OaxlRK8cusTuvMyRrQ5sRsPDQtUplJ4zQPsBNqNtuBOOK/hj5bjTENx5gD4E/dZP0WxVdYgb+D8RrAtmbCa5A3IeYCyOwTvwF/ggMWXtBlrzTy6Bx61HWwPC/nrqDYDZgw/dSYqbkDUT1UblHszlfeT0pbxXAS4i2vOuX8VqZ3Ax+CmI82q2p1tlOQTE3aA+xZoCuEqfAjuqju62Bv8AhGE+TLVdUr2EIIVaF6rUtX62O3j+gB6hu/RJosAx7k8JT6IihvRoXN6wbmeSoPfjJ9q/cmswZ8AF+BHnQkioNtnLeN8QINzxLNRqiPsB2kNHIU+JGQuWtaCyYpe0ie1qAsV+RocTLC25B/C2qj8dVHsucmFP/BsIyadL4f/AAAAAElFTkSuQmCC>

[image14]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA8AAAAaCAYAAABozQZiAAABcUlEQVR4XoVRvUqEMRBMwJ+DQ7AUC7G18QVOsPCwU1BfwEKwsjiwtVOwsrASLG19AT0UvFIE8QVO8A20ELQ5J182ye5m7xyYZHZ299sNn3MBPh50FZA2LCNgRvG5QQNEykowv9LJ4M3Jk1ANFSrPeL8FVbQIvWP4GWJTtfYt+Ep1/4NNmAG/wAuWdvoJaljGGjgCt2TC2L1B9A/BPviB8Jd04FIpnIS4xiOOQT2Ir813T/CuheMH6ozbEbmyCx02qt68AY4QbiaDT6MrPGO3tPicP8UZJs/mHOVZczoKKByAfcrjl/k76CkqaYPH8B9wrzaO+tA7gsumwbsr6D024wh6Gvc1/J6YTcEB+Am+gfvZjROWKXoB10uz9QTeVzAHfoMtaTOoBo4ukk9B8AER9jReeYLrPOhied4gW9WH7sHtyhdfku4KeAMugENY83LFVK/G0HodHEPoZxd0zmhFX7IXGIcJzUVXhuojNW5yZdHxB5kvJPYJ7vBCAAAAAElFTkSuQmCC>

[image15]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAZCAYAAAAIcL+IAAABG0lEQVR4XnVTO07DUBD0CilyzTFoI6VKEYmKI1BTpU9DQZXaTU6RjgPQUoFouACRgjhApBQUCOa9/c2zxUqzb2Z2364dK51Ih6hJD8c01OU86WQpRf3TV4O3jWcHY6tOdNjEHMwrqAe4wksewdblZXmg0SAr5E/RM4v6E3EUb2J65IIg3NzelA3SI/AB3KXtpz7wPdLWrB1wMG6h3Rcgz6E6eUJ6oQepZsOAHukMOtDO6FGh+gH4AS7djjoHZFn76iXap9KMHsBaGaJeIm/EvRXYL/S1D+BYwFgaL5O+gFk25YVvYA/MgRNwax1tL1a8I79BFNzol5Ic1G63WphUzQujK97dHi5Y2trqKjeZ9XF/6PTtH0NF1zpNuj9ojxn/fe+5YgAAAABJRU5ErkJggg==>

[image16]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAbCAYAAAB1NA+iAAABqklEQVR4Xp1TvS5FQRCeKRAdiUank2h1GkGhlohGo+YldKJQ8ShuFKegkigkEomIJ1BIaGhucXwzu3N25py9bmLunZ2Zb3735xBViftAR8kT/JxsxXqJ3mQm+VXIgV7tioroFPOaks3Q3QUrc4E6zNmufvRm3WKqFBM1fAPiATwGt0CfIRvwLfgV/CU4Alt0P5pQVqnBfC3kSj8I9jrWD6hbBnSePPI85A+UR8UyrqsFM11jXTajEOt/F6uMeRZymS5c5E1CbYljnENgfN42FHQC+yo3+INSwD3ng0qFTPJB2YNr3pnJWASPcRJy6kZzcMmhLVlCutzqLLxH0pHo1IGz4Ma9zH3wsfYc1vhHgd4ncklyA0SbEQ8xd+CFDKfFRoF4gfiGNpMQF5PMQ9Im2WdVdRKmNdLny6P42WYv0Q74E7wa3CC5b3nvT3gt8v7fUQC2sO69gf0mW4Nv1NtOJj+KU5OZEwowpBQQb7d3uLUemuMttxYkNJ40gacSYxPVs0rhQfmYUB1ZxSBxGpZNLnWmkJuoWnhQJQGyxgkjhV04OEL9IDeMKXbNv4AcN1o2X8F8AAAAAElFTkSuQmCC>

[image17]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABUAAAAaCAYAAABYQRdDAAAB9klEQVR4Xo1UPSiGURQ+LxKFRSwSSRhJMipZZCE2JQyij2wGJgNlITsDSqQo2zcYvhIbMhjEZLAom5XnvPe4/+/3fU899577nHPPOfe+P0SMRA8a7qoUJNrZZGvlFbiEOmHrkRiFsoIUJsHmIMZpKNJdCtGNJ+sE3t5IqmLoBXfAC1eWLLHmYpqHVbAbMW9aKbWplB9oBTfAXa3YTToIlbCA2fyMaYBUAd9dBsIu+sEnCC1Q14wsiGSeBe/BR/AEHATPwTNwTDZ0gbfgPjLUpUqKyJFIJVzHshJaLexf8AF2I+ZCwsUiXdgw7kQvrnkldg9MTroCcgHudChsJrwbDaeCmpZIddrheYwdJPIEE6STnmJ4NU6BaWwa0yesnOUNmqsCt8ApLKsxf4GHOoaScQxzeqWGdwx9fiJ7OUzquMuwF8XelrAmROQx1+sNRJ3gN1jhpXLQQOphFMA8qoxgvkv4+05oEza/Afbx5zFdgTVgDgI/5DY5QTHInykedEDqU+X/AHf9g8D2eCi5l23bHnCf9EL8mjGkuhOftTlD584+IPHRb+AZpfS+E17rAgqRsxrJ0fk+j8U+gmcG8zq5D1Lg5vMgTlVgj8zrtUD8b1AfixVjzSVh53alwA5RNDLiDCRnk/0EI8jKYSMQ/iHVwqI+7Bg38A+CBTdDtVvoawAAAABJRU5ErkJggg==>

[image18]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAbCAYAAACqenW9AAABY0lEQVR4Xo1TvUoEQQyesAp2Frb3IIJ6Nhb3AgqCNleI4BX6AL6FnZ1wcGCnla2ClZUPYK+FiKXN+eVnkuycirNkvy/Jl2R2dreUZhEuvrvvrsUiFT4XsVC4YQjcS+E0RCamgWp5WnSoESVKUytxK89xxQngDTaH6Kw3qOlRI0dFxGWzSeYibiFsCvwA6RaEmQE62CtsFmNT+2bSOukWxjKo0BbsGvEn2LaLDc9VTAMEjsEPYWPs7hP+STpFYffAZ+ApvF1LjCC6BK66FKI13ObSWcdOUL/sk+UZvPV/xcRIeywGH8IGiLzAvzKtVQRewN7BOjkHKnwKvH9eB4jt5E+XE7fqSPgG5K7wy6Eyhb9khWUFgS9I9sXT4g2QB+AjcFiFno8tZa/S+lXmxQ+rEH+HqfpN2mZWWY/3B9Dq3KMuTVPsx899QVqXTovGvVwOsPCP/yxXN32S2Gjb2Mnv++Sl1d/vUSe/Av0eyAAAAABJRU5ErkJggg==>

[image19]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACkAAAAZCAYAAACsGgdbAAADYklEQVR4XqVWS6iOQRh+B7nFgnSUSG4pG7LRSSSyQixJ2VBW2B2RlYUsjkOREhtRlm4LIpeUSC7FwkInddxZHBaHIh3PO9d3Zt45juPpf76Zed5nZt5v5vvm+4kEjGwUgq36tisKd9VZh2bTNIbJIy0bw1tbFlVnMQVUS4QSraR8PCHqaETOZi3F5CS+YSU4AvAoc0JlGOgEjwn3AnAnOCk6iFaCPcV4Y8CD0G6jfAJ2oz6BA6Y9sZmByybwJnixCDZgRzsOLhfianAQEw1y6fkZXCE8jAvgeXLJjgevYDxOuInd4HPwBPjT+CQ5heqmcmE0hMeZQrQGfAO+JzfmaXChNGDLN5JLvkPMschry6Kxnj1igMJKtj1hT9aBhzLZreQZqWVwY54FP+UBu6K/wf2FruVhUpJJy5sexk22xNcDVpFMUu/KK/wyU5yvH5UbUogomkqSAclp3HP0LMXc4mIrV5F73o6A18Av4FEOC+tXtDhRCxH4CPamZhsxySylrLTYivY+KXh0wtaHcq6zm3m4fEV1bzDgRvjZi0kmmHe4vC20eBGlT7JY3oikXwVnKoHJ4OykW/Bb/A2Wab79ncok7S7YBF9negOc5CVXrTP198WTqcdF3cPiMLkjabNv96H9Qho8PpA7M5WBcmHAxCQ94mJHIw5rsys0BNhwF3wAjhLiAbLHC/exYzxF+SrEBb6RO6f/Cl7Jy6VokW6GB+pIAQqxscYdIzzGRBHll4hXcr1v89vPb3JyGOtnz+EktcETXClFgenofb0Uw4goHoGL86B9y/vxwkz17bXkEpqdMjF8iLO2NCgtjAN/gLeouJHUMHtw2Z4egaIk2gCeNGEljf1u/wJ3RIeVqRtFj5DOQT0l4hX4K/GQXILhe9sLJ2+r/KPAuANOad2CB78g/GLdA++T+09A7HNOwz9+ZvmPCH+Kefu7jHiOgy1W8ilkq5p8FsXjqYpZDJ17DbYEDqvDUPDdu8AtWeC/4EctFkpNVWxCLFWj2z7+HLbR6FjJcrJSixlkvaohHKLPXuaTfbjTTamoxvbQtAq5SemiGHJpG85y/mtmA8oAbUTzP/Vy0LoMV5NwN9RwaXomKXELp7eiNlAFXSapOlKEzsUkzZHFvFVcsRfQHZmqWBQpQovxRvwBzIN8WlMEuQMAAAAASUVORK5CYII=>

[image20]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAaCAYAAADxNd/XAAADpUlEQVR4XrVXW6hOQRReI/fL8SCXFJ3iPAgdJcq1KFKEJw8uD4cil3jygFzCA1KKxIPUCQ84rhElCk+8kBQip0jEA89HOr41a/6957Jm//+ffPXtmfnWmjUza88/s3+i/wBTPBTk9Er4nbQAmsZwM8mZEyiOpeTHCes+lBCNw3Xuh1oX6uNCa4w6Wfk381yoZ2IxQNApjHAaXJnLUKWU6IlQQLcE6iFwT62R9Y8Mq8HroeSjznbKGZXV+a1Mt77gW3B2bMj4Ux8YvqBcUiiKZzkXxdgEkt5+zLK+E7zlWSqxHPxAjflGaDq7Wd2iXMcEFL3gFN+cwwXwVK3RyAA5oUxg4hgiMZcz94pu8IBUq/EO3BaLVUjGV6D76GqBcAGd4M3ClsFwuPOrWlETyiFsbRaKByifgQ/BmdDPo7wE7ipcLZS3EQrsfwO8Co70LPNIkjjQ0xh8Er2KtATtJHttvjSDFEwl2V5DRaQn4E+wHeYjZPsZsSWzdSj19SQ/zGEk420pLERnwY9KCN4VX2MxHmsGSUCebIyT4HhXN+j3CeUV1z4GbnR1FzR8/37dSNYHgR0k49kj0pl5r3f6ISwMrcPzN9jHUxPU3kB7vLIIk0n8OpIUeMhbCjwF33jtNnTiuJs9TWBoDZ69pnIBxn42eFsoCx6A/Voj3UN++s4ymmRCe0WwD95KNoFh8u2Dbb8iNcEQkgDLYgOwFjzo6rfB91K1gVrBE0VLYi8mdSsWA8NueAFzPEsXih+kZVl+9C9jWVtHN7QdkTYA/ANeJplUj5HXz+Cr/iICTa85A5NIsvuN7EehAiM+4EI3CXy42TGustFLRA3nSE67IkuKjwUfizwhC89+FLwPvgYXgPccj1Oa6VEkmeyhytvTbCD5RHgMPiJZ0PbS7BXGHqF8ctVFB/gdHfTM+VBWH0l8crWFUjEhvAHT3/PfY3gBxn42xGghOYHGxIZwQGm0GHn1q0J7ODU3iXq4K0XSdynJvbHbWQaDn6k8lgVlt02oXwul6sG3gncKp7AIahXgj8J9Uk0C8EXGSZrm2nx5vQBHKKH7Gr6BDU2MDVXgU4D/DyyKDSnSEQXmMMkPnOteYR/8mcCnFn/bPCe5CHmbaNhvZMEJ0pFDhW9KvjHHBmolwgDlfH2hKfBfSj5UHHIBIj3npqMJ74ZXpOhOUizVSMYs1aZQv0cjC1Pmk3f1kHRoqFeDXhGa6JRxVWRF0hH+2S/rYQA9nK7Whev2FzzEeLlE59ebAAAAAElFTkSuQmCC>

[image21]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAaCAYAAACtv5zzAAAB10lEQVR4Xp1UPS8FQRS96yM+oqHQiU5NL7xo9AqlyKuRvB/gRV4UCvETdEqNQoiCioRSoZAgxA/QUHJm52PvzL3zduMkZ+bOuWfunXm7+4hUFKnwT0R14qJ9W5TJyDEJtv0iW1YUFYJD3GAf8Snml5AP0FrJ01nkJKu3KDTQ6ojNQnDI6bxBM8yCXfCa7MY78BFsu4MdYlxm7VpFfYNg3wW/wVtwFRxx+iA8PbgeXH7U6QamwStb64DpGNMvuO2FBEPgB3huFvwZYHrzpghVjWKHbPGuUZkeIocLSJ3YUz6DdxtGukNB0xi/wGfEw1aqksmGA3COrbfAE7I/2x7Z21RwiyOyp+9YgVtcLPR01R9PZBsseEG04H247iKlfxDMW2KK/1D5pqSIdq2DM5kuseA7uuUb2SZjmaMYjINX4IAXVFcKV69HtsFaopcDpikEZ+CKzwfUdXH5CfAS8SfmpaDbYZHsqznP/AliVfdQYT6iTWRvEN+TffXM38UGha82s1WDtDpFJthteJob4yS7vWoTsS6oUgWfFCZ+XAFFV05VSf4GPOGGyJRB87PUmJoXUgRxAx6JBuKPL4bwFMrp+lbgaGKMPLnTNXkeiu4lcQMFogHfVHP7P6o6Ml6WRPaLAAAAAElFTkSuQmCC>

[image22]: <data:image/png;base64,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>

[image23]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAKkAAAAcCAYAAAAa0p/pAAAIbklEQVR4Xu2aeexdQxTHz6DWUmLf0iqCWBJiX18aQvxhiSiNJVo7ldh3+rMlxBJbQq0liD22P4ilqdqpUBRpqIi1xJYgiNT5vnPn3ZlzZ+6d+95979dKP8n5/d6duTNzZrlnzpx7iRY1jE5YOBE1lbJx3S9jWcCypc74vxEfgoWeHlTvoWh3dNlgebH1WH5mWUJnLHSU9qM0M06XxeI0XuFw43co3L1waoNMYnlMJ/ZCHY3r3NsvGtChgSoGiKctLtyE4eiK1qHI3Synk1jUs1mezLPKC3ZPM/U2UUsTddQgqbmxLI/qxAR2ZblFJ/afpD61Sb+zwFyWg0gs6gSW2X52/6mp+z4sV+rEQC0lc9ak5ei1vM8yLC+zjFHpqeCAcYFOHDAHkhxyIC+yPF8iM434mgt4HG2Zb1lGOMOKh3YBXz/DskGePGDS53lDkjlcWmdE6M+cleoby7TpBj9iN9GtLKfqxBosxfIJy846oz5RHVN4mmTBXaMzIowmsZLQHeUOcPKQfh/LOixfsKyeiUdP2jYHjMws1mVrnVFC2py1O5jWS1T0Jss/JIP5AYlFeIXlmyzNytpZmSLhtjZl+Z1lJZ3BTOYi843Ue1on1anH+XkWeT5bTcK61cJI3+eT6Lubyi5jRZZnyXd3prEck/2eR7Kgr+rkWrrQu6TI0SwvUD6Xr1Nu/d9h+ZrlYipGG05hmanSXLDLYKdwH0LoEZkzaKi0LFFaA2Wh/Po6gzmYZLHpDlQBq3OnTnQ4jqRN+DFlYLvBfVv4yTV6F7w3lFbK/iR6wEqEHrwYK7PM4eZGZdezSPoE2KKam/l/K7vuNzA8EA8eiYkkfbtQZcGAHaXScgwdwX/fJzFILpE5657lWf4gebpCwHy/qxMT+IplvE50uJ/lF5YldUYAWJwhnRik9tqrxW0kg/+4zqhgHMsmOrGU5vuBhQTdMe6aNUnyvnTSNsrSkNcN6XOWwN4kyrjO7ros52a/V2C53cmLkw8stjDUuVUnxQcL83uWB3VGhHtYntCJwwDGwvqZCCGFcRZY82utayaT6H2szmD2JMlzt/YjSYxInPLONTpn8Ieg4DbZNZqeynJy544IJq5l+0RsZKtr0z5f5exI0uakrKfw8x4h8Y/2cO6z4AFKCdPcQFKve7rOxKjrtsywBTtEu9Rhe5a/Myk/HMSobqMfPEXSZ1hIDawr8vZy0q5jecu5doFP/VImGI8QqXOWxGtUnDwssM29uzTlAw2H+1+d6HARSTsIZp/AVcG3wan3Nwo/HLACcNCpquFyeinrgQA89P+UstBMYzXHSGkgdI+k4ZSOc8U8L49oDMslLD+wHOpn0cMsz6k0sDHl7s4bLA84eS7OnPXGKiQne4RYLFic8Cc1OFTZE+KrJIctHALgy+oT7xks39mLwNgh7oanDOEpHMwAAsZwK0bZ+51yWMTQM+nwFmivFH2/vu6QZ+DXDJKxgMVJI1qxT9VtVfkBYCGhK1ysdjyX5SeSRXQFhSM32KpD7hgs5C4kMV7UaSMVGp4zkzxnllDfbKAalsECB3+ac+2yA8tfJIctC6ziHOcawJIiZBNiVcotNrZ3PHEjvDsyHIUPI7m/Vof7DLZN9BGHTvSpQGjA69F7DRlXk4wfIiqptcKSQmIFELL6k2VkKN/UmrNABQ43kVS0k5M2kiKDTmL58CS6XE9iWV0OJ7F8IXDiR5u7k2z3n7Pc691R5CSqcuKF3CdNk+lSrGvwkcghOrGfyHSWT2oBQ++R9BfjXVG6c9LAuSS03QNEfD4jPW9+xd6c2azytsPAAqIiNBonrxmHmyl5RvtNCcIWLdX6viSDgmC2Q/smxAWx1djQE+q0DjYWN06amvNYMNCN0s2AOcCSXKoTE+vEuMCfRRSlLnDR4L+nMppkLgqHmApd8a4+FpYcb+RgCuOGhY+x0DhzVtFSFEObUVt5g1NfCjDb2N7uINniEfjFfxsVcBlLMjCh12kYLNcHRvt4YrFoccrMH5i8b2gzFN9rhsAYBpJcsJU9RJW3RcFYIhRUt/zlXATWG7tPJVnlE0kiG9d6mdVwOfoRPwpKmrYf/nF2hd+hj7drzZluYxzJlm23AMhcivuhlu1ItvDldEYBaXEey/F+Bi1LErrBlz8WOOFw5BFlgAsQAgsbr9pydK/6id8WWw+D0Iw/Dk3rE6+vRWmL9ESWDymfY941DeY91XpbQwNjpsGLARgWnOz3U3mW2UbP2QBA8BoHnVTuouD72zq0ZwqvIPFwrOXnDQuIcOD7hvbr4/g6KgD/btvsNz7Rw9jYCcR2iR2pTLBlW1qUtkibAIbmTC8lrdOFOUsr1gvSAnzHG/0MEG0egW4oiq99esDAGpd+xR7TwE2P3VMDxBpnkOwodcDO9VH2G9YXIRts9Vio3dCiRhdp6cjAr8S7eZ/SIm0q58xSqKqQEMW7E2Yf/gUC7W+TfGjRoaJOxNnO0YnJmLZ/iq0+9JZkcEgneVGZCRX9dUGQH/HdXyn/xA8HJryFw1aJ8J9Dcs0tUwzKOyTXkwLcMzwQbvTHIdjWcM9ZUKki+W2rkXxJE/eDyqucQvVOsmmUtxkCWy4OeC2Iyf4HhH1tc74hg0MV3uJYf9D1tbGzIKiOLXENkrHR2zuLca/tV1OgRfIdapz6/YtiZIFOp6oIUE54zhrUqR/g5QAmrS74hC9xS2xmBCK1ICRmF1sN6XwrgLd37pde+H4W8VzEV3ForEuL/K+V+o6R70WHCqnFASvMWfGWxQyALobdLwJriwPlkJeaBt7OIayDt1xDJAu2HK/tKt2r8ptjcC01TV80b7LSJutyaLTaRitbTBW9DTdK91bDYMl1XZS0rkNyv5Jv7BW3oT412qdqFzPM/AflXZa0Mn1gpQAAAABJRU5ErkJggg==>

[image24]: <data:image/png;base64,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>

[image25]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHIAAAAaCAYAAABreghKAAAFwUlEQVR4XtWZeehmYxTHz7U1hsSMPYwRZSR/KJEMY03KmtTEX0M0Sf6wRfayZS1bijKNJUMNQpihxhKSXYikRJZkSUNI43zvee77nuc8y33u+977y+9T5/e+93ue5zz7ct8fVcTUf/qi12AzxhC1DmIGwpD0WliVCBdXLWWpMkwUYKJMs5v+V/MwjKs4Cyo7MwzREalVW0KQ81q2B63YE7uwPcf2G9unbDewbe6l6IdNSNrxMts7bLdQP+W4ztLLL+i/qGRoTzElC7mE9fy50joCuldlS870GX+exTaf7RK2DWxPe6n64VG2h0gGdA5JGRjUVg5lW8P2I6FyFf3Nn6+xbealIvqYG4PK/8P2NtthTl/C9qbT4UdnrmM73PlRmdfZ/nX+b9kudT7MPDxDh33PdrbzNeD5LxL/ryQrIcZqkjKyA5kawxb9SrbrPId0OOp0vNHTwSKYpCeSxNxeafs47UA8lIQ+nSTDs9bhOIntfbY95TEI+QpJ/t0Cj3AT251WZLYmyfe5dSjuIRn0Ta2jpqJj+O/dVLoiU+iK+414hu1ntsVKa/prhdLKiXcSYv1gNKxMTNDLjJ4E+/AvbFiR2xnfIraXInrDNiQr8i3rUCA/4hjqFqGT/mwePA/R/iR5400n2pjtDZK6+QOZypGiTh89s7HaMWjLlIaJzVq1Kj3+nfmQ5Py1YFxetGJNrEDW7iOp8HIl70Cy9e6oNMspJPmuNnrDFlRvzQ1B6diakX9XoyMhGrDQ6CMq2XovcI/RFZno6MX8fWkzeC1gq1vKtpE81ukvJ6nzNU2iEWG4M9gOtqKlkqMDg2nBkfOlFWvCsmqwdaBy69wzzjdsK7s3CQIkELZM5DvI89GoHOz9t3oOn+a8OcTomFC4YITIAGxFsgs0W+5oIIP2OUF9/E5SJla8Isjp8HTsApiYP7HtFLo90CcoB6sqQJox+o47SmwgcY/4xopt4HaGgvdle4ptP98d5ROSiroZG4CBPkELpt04P1HmaUrDdf9h9TxC5UU+bHENrStS8SrJeTTPOgrA5MJRcpR1RMCOhgHHrkbJ2gh/UHxFYhC/smISV8RVJJ2KzEvG3iR7kKR/0joU2PexelIs58IR40KlraD8dr6A5L3OUdd+PX+Ygcx23CTsTfIuictOBl1ucR2+ZvvIisx3JO+UIZnQJ5MMDG6JJZxHkv5860Apldxy11qP4ViSGLe7euFMwbmbYxXJ1VwTXZGaTLtLwKUOW+qZY6kkokvTnvRdti+sSDJx3IouwJVzB3nnXWvp95KkP6ARTA5sf6f6UgBus4jxOMnryG2+OwoGbUMl+WKmb5h9gHMYF6+LlIaBxTtmJzI9ej+FZ+lckvbcaPQUo/BY2rnzznIFSUE4U8dIOPzYgHO2DVyqEAM/NOB9yWzDmaaP2ZYkRnZFKnCxw000iyoZExyTVuto382N5uPVuejWyhxN0oYFSsMPAdDMpcxguggXDM5UrS7qOmEvksMcDW3Are5ckhU21xaSAFsKDnv90t2KCr0zSYMfGUtJkC1xa3X4dcZAIC3eZ2EfkJxbeFG3v0RZsrfWCPhtVe9IKyt5LSygoiNI9uD3SArFz3VrWK9/FioAg/kA22NsL5CcidjakkM4doy+Pc/frx/JbejIFT1B0lHNtoqLwXEqRYzkrdUPXdO858bsSJc0hbm1+kQ6CDvhOWx3kWy1FzutXyIFzwjDljtE9LKYZanGdE0/u+jaulT6lD4R6WBpTxsuZz5AOlFECihJo9Hpx9+7RtGk8qb0CQnCBcKE9BWnN/53FepMvAVxtReyobPOVneC6H8G2umQqSSpXsHd0g+Djj9RWdlMWWc3pg41dYAeOquYYaP7pMpK6VMyedjJcw5DyXRI6WnqHMXZihOmSYZIOkrxA3RrWBnZcEMUqJkmdHHekknWB9nYkYEsoThhCyVxStLMJJH6ZOdjoPvCf/ly/5vRVO79AAAAAElFTkSuQmCC>

[image26]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAA+CAYAAACWTEfwAAAEcElEQVR4Xu3dz8tsYxwA8Ed+F4UUsUP5tRL3CgtxS2FBKSvlYsMe2eAu2EnI4m6IUiwICyRFFqKI/AFWfixkYU3i+Tpnes995r3zvjPvmZnnnPP51Lf3Od+Zd+bMnDPnfOeZ55yTEkzSKWUCGKWBfdYHNru9mdDrntBLBaAOde566pwrAAAA6JfvvwDs2O5eYbvPDgNW4Yenwlni5CyuSlgQALCCGnegNc4TAEB1FE2swnpTCQsCgBXZhUC9NvL53MiTALRscwAAYJjOyHEsxw1FHgBgKPrpm+znUdbi5xyfpXUXbBW/AdTOygMA4cm07oINqJzCGKB2CjaAA1P0AuulYAOGTrU0HJYVFRjmahgF26EyuX3DfDOZKusrm2adg6mJgu1wmWT/bDYBgHV7JseRMgkAsE3vlok97b8L5YEyUbk3cvyb468cX554EwCw2P4LBJZzvEz07PIcv5VJAAB2M1/0vpDjtTK5hJvaCLfmeLNtn5bjpbYdHk7NFQQAACZmvgBb1i857i+TS3iu0346x4Od6cc67Sty3N6ZZlUHX+ZMmNUHoF7/pOZSS7+mZmxWFFYzMX1eZzp8neOHHDfmeCfH3W0+jpx8b3an7PQcV7btc1Iz5qvr7GL61WI6XJyaeThZ3LFzV/pip83UWOeB2kXP1iNtO8aSRRHUFcVc19Ecp6am2Po+NYPuo4ALd6bm6Mnd3JXmH7v0dpmAg7MrBmD4/uy0r0rzRdXvxfRM/Jx5WZlc4Js038NW+rxMAABwYoH2U473O9Mhbj+3bceBAs+n5uCAP9rcvTkeatvR83Z+2y7F4zxbJguvlIkRuyTHRWUS1kU/I8CwzX6GjGLsuzQ/Xi0KrevadhwUENOPtn/Dp2mnoIv8y227FPe/rUwW4v+n4vEcZ5VJBkYVxGBYWWHsXs/xYZlcYPkT7DbuKRM9iWLzWKrvQu0xpi880f79anYDAMCybs7xd5lc4GQHHezlrTLRk49TcwRsbQVb/HwcZuee22t8H5XbdP/Fpp8PgPpdmOPSMrmLOHXHKj7JcU2Z7FGcbmQbBdu17d8Y99cdnzfrXev6qEzAnlRtMBU+7UxC3wXb1Tm+SLufN650QZofq1b2QsbttxQ5AIBJ6bNgeyo1V38I36bFPYNHc9zXtv/vVWu/Il3f5mbiYI4zixwAwKREwXaoTK4ojnZ9McfxNN9zth/l1R3GR8c9ANNgj9ezKNgOl8kVfVAmlnSQ67ICADVTwh1IjBk7UiZX9GPaOVddXL0hxqgBAAAA4zf57pnJvwEAAAzerKZV246cBQwAAAxc1V9rqp65tZnmq66NpcDUWOeplpUTZnwaAMbFdh0AAFiW7xEALMeeAwAAAAAAAADYDqMWAGA77IP74p0EmCy7ALbNOggAAAAAAGzLRn+n2OiTAQAAwMD43gwAAAAAsE7j64Ud3ysCgPrZ/wI9s1kZB8sRYNLsBgAAAAAAAADWxS+yAGtjEwuwZja09MF6BAAAAAAwPov7fv8Dcuph03uwC0YAAAAASUVORK5CYII=>

[image27]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA8AAAAaCAYAAABozQZiAAABUElEQVR4Xo1Sq04EQRCsMTwEBwIkCeYEhj/AgcSdwvEhSIJG8CckJHcKQXLBIDAkJDi+gAQEuRy10/Pc7tls5Xqmu6p7unfmgALO9J34eRlAS1e8ax0YutVUXIx8g9EYk4P6m0tYk87IrMmtKLzTX9D/Jr+m/dGWtCfaynWcw2kudXjgek1htzh1Dl/spkWjE9oPbd9HFCbcHnuzbIWkj8Rk+a1MvWJwmSIRziHj3SdexG3KixwCU26bwY/sDeR7ZzWPDdqxuNWkVfgM6bzXsZ7v5XpkIagOO5AbfqlygledUQphu4CMfBsJ1TQSSgDuIMVnlujR4im8cv1F91zqY9N0miOOIH+M/BxNOP87gH87X/AFGbmzz8Af9koaQcLAJSVfOtdoERavDjSQ+V6GEsJIg4fGscdANRiFehgNxRnzGlTh2Wq7OC5257KqdXkO/3qzKYCfN4CcAAAAAElFTkSuQmCC>

[image28]: <data:image/png;base64,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>

[image29]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAC4AAAAZCAYAAABOxhwiAAADaElEQVR4XrVWTYhOURh+j5lChsloihKNUhQLNvKzQsqUZENJUqRspBgbC42S3xQLZcWMiGEhJD+loUj+iY1kS7OjpGx43vOee/7P/e6MPPXce8/zPu+55/9eIkDxJQAryur6HhS857icICPqvIw+doyustid61vY6wxyoZyWIh62tJiUDUK5YKK6iCAXb1o3YxHiV2G6DQ5hKnej3Bab6quoQbPELvAciDbQEHgKnBY4qorkpmbg8gicYzSWb4JnQl8JJqMAP1Q9W80Fx+H5DoRVViHqA1+B7Z4WVHgIJTb5Fc/F7TfYYV0uNnpwkk5Ms42ymmSwRBGRZ/wLuEZv5kzqAC5XIpGn6I+5jw3Zd4Xw4tvBT+BkG5HgGzxs8J32CZ3pJ2nkNXCCkffCcSMw5qBoHuLzq0IG3eAyV2RP5JMiLxFuw1twltGX4PoVnBjkeI+8LH6SJL4D94NPwenOQsn7DLoh38d9ti8aaxfuL3FfGKg5KKxjRR9BbsMInHuIR1v5nY4g1amVuHwnbrwknwTba15F3uj1gA/BTi/I65NPB663KfhweE8ygMy7JDMWIG7TcbAf6gC5xPMu7NvdV9UDj8wDBDpJjtGL4ObI0wobwcskp0nVBqxxmuKbPKgDuFzwhOXgZ5LEdbqRmZZa0cVWkDR+ENI2qybIVsYz8wEcb+IziesixW044RsrTAV/gIvDBqoeJfrhSgkQv1vKfN7ew+NrlPlj4oXysL8sioZJ1rUVSHeCnoOPne6wgGRkJ8UBJdN9NNYL4M11HfcdIJ8Gw8pf8/HkpL3h06M31HVhJ/jEVyvwufkLlrWZynjD9eqn5G8uKPOavgQe87SlJKeNv2HrMAweiUWSfecNXtiOXeA3cCvxp1e+lvvMiCeIuwAMgmfJhKq4krOZp9nMZibTgTs6Ah4k8bfBvZ4kv6OcqfQm5A/OM/AWypvCcBHwqdNUtmwhHrVa2FQsW/0Vf6H0xqQ+5T6IDZBpQiAF4/oPGFMVrZJaxRm+p4k/QJXQKlHirVwOyWYsoKEtgMqnWS0X/J/g96XvNEoaaIzaMQ/l+JMeJ9VH86h3uWjkK6ZVAT1ccYNqKilW2ACFesZcZdzsFDkt7Lu+1vTXIa9aFMJ5WatxqDA8SSmDxMCCEdP+OVQBbZdC7P0LSfxmvEdvJUIAAAAASUVORK5CYII=>

[image30]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAJsAAAAWCAYAAADXT+6KAAADZElEQVR4Xt2au6oUQRCGewQD8QaGgoEPIJqYiZgIBqJGBmbGHvBhxExMFBPFRDE5kS8hCIKRoAZeMdbq6Z2Znuqq6qrunt05flBnd+r/q7pm6L2dXecq6TYx3I9vF0FoLkgL027ldp22w/bmRStxC3P5gZy+CkxDYjM+DsyyHecqpW23pTgM8QLiDBZao7scwSV7GbVPM5oCe6WuArvwMUWnMZWi7q0z6lyBhxC3xqO08uxwJ5UQwxWKjUwRmaaSVM6AXC6ogtSMaI1mywmNBEmgrIriDsRLnASOQ1yBeATxfS4hqmfRNNB4MKGmpLKIrS2kYT6MNJqkkcQPEFQs9ToE8QniGspfgPgC8QziHcSPScLt8DGVqaFttwllX6VtTlGRQOt+ZYxTFI5zA+KDk8tfuXGzTTapgNM6UqF6Uj7PJo9k/OiSyZjjK5qx7gz6MqyeJxAPcBIRbbYCGl+RWTu86eaHAoJTkKwkrZKEgpKalfIeYg8ne6aTnDab6cRN5t1ygEYlEeYXpDqMjU9C/IW4iYWBTb+KZzbjRAcM29kFt61Gw9CR78wrgXyHes67sNkuYwEx32yqiVSmFEsZ8lpKF2MVQ3AQwxGpAUGK0Lk8F53fbJ07hwWE32w/cZJGv7gN9NFCvYzaiMjV5XQCa4nV32MsMtpr6J/ZunArYdhs7hLEPh3dPpxcnHsDcazojJkSJh2IPrKKPg6qKMqlMs50GX8K+emdSFUj9ZQ0A/6rKe3L6C+czEHNSOUGJG1bpDPMN4gKqz9Dvp1xBy+BYt2jLmy261hA+M32GydlwuqKGVYLnh0f28hX5x0TFm81DRf7CHEfJxH+JfCPC5uzEMPEpJVMuj7PSauBGZBJrwJhNkHK8hjiaZzYNDsF8daF70T9s5+Pby681/Lvy6rhh+YVEpPdZC6jYAmyhEzGZA0VbHpLS/RaakgzE3chvrrwE6MJqWKbWOaweLfNOJt2SK3Pw3m5fCUVbU9AfIa4jYX/iYrrk2fR5q1Jh00zZej6dO4e/H2N07XoFqex1WrcGg8DU8qkA6K4Fsh/rGQRa0Qx4H9m5H/PdhULCYpmeZo0ccV9isqKimT6lkRfItWOiuaWUto7Zo/A/edwezoSy6AXGsnIOyXMtqsJ26zru7TppCG/0j9Cejy+k34MHgAAAABJRU5ErkJggg==>

[image31]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAA+CAYAAACWTEfwAAAEyUlEQVR4Xu3dO6grRRgA4Lk+8FWo4EW9jQexUgtFEAULH6CiWF0fjY0KFhYiWoj4ABEuNtfKUryg+CxsREFERBF8lCJ2ogg2IlipaKMzZvdk7pwkZ5OzSfbxffCT2dk9J8lmd+bf2c0mBAAAAEbmUFkBwJZokQFoV+OepfGCB7faU632VwAAQJ/I+4He05DBMDTYlxssAgAAsFGOUwAAADbGIRjQK4NotAbxJoD2bKdR2M6zwnrYngHG7UiMj8tK+qzDXXuHXxobZ2ugAZsJJI/G+DbGP+UMAAC65Y+yAtbCwTLQfVoqOkvCBoOl7wEYCgnb2OjDp6wLAHpCwgZsgOwY4CAkbAAAHfdXcOgLAHTM7WVFi64qKzrs5hhfxfg3xg/B/dgAgI44I8bVZWWLHojxQVkJ0F0G2PvDZ8V4fF1WZC4Ik9GmeZ6MsVOVn4nxUFU+P8bRqpycyMoAACzhsrA4Ibs/LJ7/YVZOpw93sukrsvKDMU7PpmH9ygPvchoAOuTlGH+HySjXnzGejXFdNe+lGN9U5dq5MV6J8VmM32O8V9W/H+OxeqHocIwLq/JtYXFil9xXVkQXhcnfzYtbp4sCAAxX+sbjlVU5jXRdns17N8ZH2XTyRZiOnKWk6eGqfCzGLVW59GLYP2F7pKwAgGEwhM/BXB9OvpYsJV9HsumUsKWopRGvNLJW+y4rL5J+LD0leos8X1YMmV0XAFY0wk70rhinVuV0TVk5CpZGxr7Mpu8M01G09HhHjGur6fNinFaVS+n/pltiLHJPWTFg9aliAIB9nR2miVRKzF7N5iXplhu/ZdMpKbu7Kv8c4+IYr1XTb2TzSum065llZWYnnHwqdgXdTLfnvKpF6wKWNGcrA+g87VebfiwrFni6rGjoeFmxmj0f/I1h8gWJbXs9K9df6Lgpq3u8enw7q+u8PWu7U7r96gCgbU+VFQvkSUhT6TTqT2VlC9IvKLwZ4/tyxhz1qeG2pcwhH6Wsr9V7rno8K0xvTPxC9ciSpGcANS3iSMz8oD8tK2ZYJVlLPg+TU7Prkm430kT6RYc2nRImp4jTrVHyEbYbsnIiSQMARq9pwtb0urL0RYtPwuQWKIvUiVi6V92lVbm8OXB6znQPPGAfMw8lARiMNhO2d8L09iS/5DNmqG8inK4BvKYqHy26nfSFj3TLE4D1GWS2O8g31SHWL2s2YxNrK2FLv9zwa5hcg3b80MynWihdq5Z+W5VOWPbjY1RsHsBcGoh1aSthS9eePVFWLuHeGJeUlQAATH50/pyycoY5CdtuJp0KJ8LkW62p/FY9AwDYOENdIzUnYWMj7HbQYZ3dQTv7wjZi3O+eXrGxwnrYtwAAgC1xOEKH2BwBWIqOAwCAXZJDAAAAGAmDAAAzaBx7yIcGAACsg2MN+s0WDHvZL4At0fzstfQ6WfoPAOgcbTlAH2m9AWCjdL1r1HjlNl4QgL7T5B+I1QcDZecGoA36E7bH1gcsQZOxDysIAFakE4X+sL+yGbY0AADAgQEwdJo5aIM9CWDYtPMAAADAKowpANBTujCAXY2bxMYL9t+I3ioAPafPgpH7vxGY3RLMrgVom9YGAACGZNwZ/rjfPQAAQC84dAOAOXSSjIHtHBgSbRoM3n+mE2gTu/mVigAAAABJRU5ErkJggg==>

[image32]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAZCAYAAADnstS2AAABR0lEQVR4Xn2Tr04DQRDGdyUhBASCyioSNMHUtQ4sEoPB8ARIeAFeAIVAItoERFUTHgGDxVSSYJDlN7N7O7N7B9POzb9vZue77IUQg4qYqL8sxWklIQugwtVBlP+AxH+ml4qB1Ejod2u2aCTxGK6JpMoE/cDfYJe+UIvl9gVMeOuqIu4wA1+gG+JZyaj4E4zEE+R+8LZqliHsog/4aworaN0Rf1F6tkHJ2Ubf0BfinZynUcldFXC296kQD902N0HJxXHJUDzgKSRWLif6yuPdA0XOUHk9s2gkhL2scArqBHvdVfbo+saeKzaGI/Qzg0eQfcSOdXTumKJL9mOVuCB3jJWGOXopgITTZ+pKg12qcwzofbmu3ZW1AX3xY5sL7iL/KVm6HO5XScPa8/6cPJDo1nGJfrtq/U3md2+YWmy/Xs0I1GcbD8v/AgUuI5KV9dMLAAAAAElFTkSuQmCC>