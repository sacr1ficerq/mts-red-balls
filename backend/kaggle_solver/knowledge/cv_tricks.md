# Computer Vision Tricks for Kaggle Competitions

## Data Augmentation (Most Important!)

### Albumentations (Best Library)
```python
import albumentations as A
from albumentations.pytorch import ToTensorV2

train_transform = A.Compose([
    A.RandomResizedCrop(height=224, width=224, scale=(0.8, 1.0)),
    A.HorizontalFlip(p=0.5),
    A.VerticalFlip(p=0.5),
    A.RandomRotate90(p=0.5),
    A.ShiftScaleRotate(shift_limit=0.1, scale_limit=0.2, rotate_limit=30, p=0.5),
    A.OneOf([
        A.GaussNoise(p=1),
        A.GaussianBlur(p=1),
        A.MotionBlur(p=1),
    ], p=0.3),
    A.OneOf([
        A.RandomBrightnessContrast(p=1),
        A.HueSaturationValue(p=1),
        A.CLAHE(p=1),
    ], p=0.3),
    A.CoarseDropout(max_holes=8, max_height=32, max_width=32, p=0.3),  # Cutout
    A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ToTensorV2(),
])

val_transform = A.Compose([
    A.Resize(height=224, width=224),
    A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ToTensorV2(),
])
```

### Advanced Augmentations
- **MixUp**: Blend two images and their labels linearly.
- **CutMix**: Replace a patch of one image with a patch from another.
- **GridMask**: Mask out grid-like regions.
- **AutoAugment / RandAugment**: Learned augmentation policies.

```python
def mixup(x, y, alpha=0.4):
    lam = np.random.beta(alpha, alpha)
    idx = torch.randperm(x.size(0))
    mixed_x = lam * x + (1 - lam) * x[idx]
    y_a, y_b = y, y[idx]
    return mixed_x, y_a, y_b, lam

def cutmix(x, y, alpha=1.0):
    lam = np.random.beta(alpha, alpha)
    idx = torch.randperm(x.size(0))
    bbx1, bby1, bbx2, bby2 = rand_bbox(x.size(), lam)
    x[:, :, bbx1:bbx2, bby1:bby2] = x[idx, :, bbx1:bbx2, bby1:bby2]
    lam = 1 - (bbx2 - bbx1) * (bby2 - bby1) / (x.size(-1) * x.size(-2))
    return x, y, y[idx], lam
```

## Model Architectures

### EfficientNet Family
- EfficientNet-B0 to B7: Scales width, depth, resolution together.
- EfficientNetV2: Faster training, better accuracy.
- Use `timm` library: `timm.create_model('efficientnet_b4', pretrained=True)`.

### Vision Transformer (ViT)
- Splits image into patches, applies transformer.
- Better than CNNs on large datasets.
- `timm.create_model('vit_base_patch16_224', pretrained=True)`.

### Swin Transformer
- Hierarchical ViT with shifted windows.
- Better for dense prediction tasks.
- `timm.create_model('swin_base_patch4_window7_224', pretrained=True)`.

### ConvNeXt
- Modern CNN that matches ViT performance.
- `timm.create_model('convnext_base', pretrained=True)`.

### Using timm Library
```python
import timm
model = timm.create_model(
    'efficientnet_b4',
    pretrained=True,
    num_classes=num_classes,
    drop_rate=0.3,
    drop_path_rate=0.2
)
# List all available models
timm.list_models('efficientnet*')
```

## Training Strategies

### Transfer Learning
```python
# Freeze backbone, train head first
for param in model.parameters():
    param.requires_grad = False
for param in model.classifier.parameters():
    param.requires_grad = True

# Then unfreeze all
for param in model.parameters():
    param.requires_grad = True
```

### Learning Rate Scheduling
```python
# Cosine annealing with warm restarts
scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
    optimizer, T_0=10, T_mult=2, eta_min=1e-6
)

# OneCycleLR (often best)
scheduler = torch.optim.lr_scheduler.OneCycleLR(
    optimizer, max_lr=1e-3, steps_per_epoch=len(train_loader), epochs=30
)
```

### Gradient Accumulation
```python
accumulation_steps = 4
optimizer.zero_grad()
for i, (inputs, labels) in enumerate(train_loader):
    outputs = model(inputs)
    loss = criterion(outputs, labels) / accumulation_steps
    loss.backward()
    if (i + 1) % accumulation_steps == 0:
        optimizer.step()
        optimizer.zero_grad()
```

### Mixed Precision Training
```python
from torch.cuda.amp import autocast, GradScaler
scaler = GradScaler()

for inputs, labels in train_loader:
    with autocast():
        outputs = model(inputs)
        loss = criterion(outputs, labels)
    scaler.scale(loss).backward()
    scaler.step(optimizer)
    scaler.update()
```

## Test Time Augmentation (TTA)
```python
def tta_predict(model, image, n_augments=5):
    predictions = []
    for _ in range(n_augments):
        aug_image = tta_transform(image=image)['image']
        with torch.no_grad():
            pred = model(aug_image.unsqueeze(0))
        predictions.append(pred.softmax(dim=1))
    return torch.stack(predictions).mean(0)
```

## Loss Functions

### For Classification
- **CrossEntropyLoss**: Standard.
- **LabelSmoothingLoss**: Prevents overconfidence.
- **FocalLoss**: For imbalanced classes. Down-weights easy examples.
```python
class FocalLoss(nn.Module):
    def __init__(self, alpha=1, gamma=2):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
    def forward(self, inputs, targets):
        ce_loss = F.cross_entropy(inputs, targets, reduction='none')
        pt = torch.exp(-ce_loss)
        return (self.alpha * (1 - pt) ** self.gamma * ce_loss).mean()
```

### For Segmentation
- **Dice Loss**: Overlap-based, good for imbalanced segmentation.
- **IoU Loss**: Directly optimizes intersection over union.
- **BCE + Dice**: Common combination.

### For Detection
- **Focal Loss**: Used in RetinaNet.
- **GIoU / DIoU / CIoU Loss**: Better bounding box regression.

## Object Detection Models
- **YOLOv8**: Fast, accurate, easy to use. `ultralytics` library.
- **DETR**: Transformer-based detection. End-to-end, no NMS needed.
- **EfficientDet**: Scalable detection architecture.
- **Faster R-CNN**: Two-stage detector, high accuracy.

## Segmentation Models
- **U-Net**: Classic encoder-decoder for medical imaging.
- **SegFormer**: Transformer-based, state-of-the-art.
- **Mask2Former**: Universal segmentation model.
- Use `segmentation-models-pytorch` library for easy U-Net variants.

## Practical Tips
- Always use pretrained ImageNet weights — huge improvement.
- Normalize with ImageNet stats: mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225].
- Use larger input resolution for better accuracy (224 → 384 → 512).
- Ensemble models with different architectures (EfficientNet + ViT + Swin).
- Progressive resizing: train at 224, fine-tune at 384.
- Stochastic depth (drop_path) regularization helps ViT models.
