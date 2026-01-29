# Dashboard Presets & Widget Resizing Guide

**Date:** 2026-01-29
**Status:** ✅ Fully Implemented

---

## 🎉 What's New?

Your dashboard now supports:

1. **Layout Presets** - 3 built-in presets + custom preset saving
2. **Widget Resizing** - Small, Medium, Large sizes for each widget
3. **User Preferences** - All settings saved to localStorage (ready for database migration)

---

## Feature 1: Layout Presets 📋

### Built-in Presets

#### 1. **Essential** (Minimal)
- **Widgets:** 4 core widgets only
- **Visible:** Statistics Cards, Energy Flow, Quick Actions, Weather
- **Best for:** Clean, distraction-free dashboard with key metrics
- **Widgets visible:** 4

#### 2. **Standard** (Balanced) ⭐ Default
- **Widgets:** 8 core widgets
- **Visible:** Statistics Cards, Energy Flow, System Diagram, Energy Chart, Weather, Quick Actions, Goal Tracking, Billing Summary
- **Best for:** Most users - balanced view of all important features
- **Widgets visible:** 8

#### 3. **Comprehensive** (Full)
- **Widgets:** All 14 widgets enabled
- **Visible:** Everything including Device Overview, Alerts Summary, AI Insights, Peak Demand, Environmental Impact, Load Shedding
- **Best for:** Power users who want complete visibility
- **Widgets visible:** 14

### How to Use Presets

#### Apply a Preset:
1. Click **"Edit Layout"** button on dashboard
2. Click **"Presets"** button (shows current preset badge)
3. Select a preset from the dialog
4. Click **"Apply Preset"**
5. Dashboard updates immediately

#### Save Custom Preset:
1. Customize your dashboard layout (add/remove/resize widgets)
2. Click **"Edit Layout"** → **"Presets"**
3. Click **"Save Current as Preset"**
4. Enter name and description
5. Click **"Save Preset"**

Your custom preset is now available alongside built-in presets!

#### Delete Custom Preset:
1. Open **Presets** dialog
2. Find your custom preset
3. Click the trash icon (🗑️)
4. Confirm deletion

---

## Feature 2: Widget Resizing 📐

### Available Sizes

Each widget can be resized to three sizes:

#### **Small** (1 column)
- Icon: Minimize icon
- Grid: Takes 1 column in 2x2 or 3x3 grid
- Best for: Compact widgets like Weather, Quick Actions

#### **Medium** (2 columns)
- Icon: Square icon
- Grid: Takes 2 columns in 2x2, 2 columns in 3x3
- Best for: Most widgets - balanced size

#### **Large** (Full width)
- Icon: Maximize icon
- Grid: Takes 2 columns in 2x2, 3 columns in 3x3
- Best for: Charts, stat cards, system diagrams

### How to Resize Widgets

1. Click **"Edit Layout"** to enter edit mode
2. Hover over any widget
3. Click the **size icon** in the top-right controls
4. Select: Small, Medium, or Large
5. Widget resizes immediately

**Note:** When you manually resize a widget, the preset changes to "Custom"

---

## Default Widget Sizes

| Widget | Default Size | Recommended Sizes |
|--------|-------------|-------------------|
| **Statistics Cards** | Large | Large only |
| **Energy Flow** | Large | Medium, Large |
| **System Diagram** | Large | Medium, Large |
| **Energy Chart** | Large | Large only |
| **Weather Widget** | Medium | Small, Medium |
| **Quick Actions** | Medium | Small, Medium |
| **Goal Progress** | Medium | Small, Medium |
| **Environmental Impact** | Medium | Small, Medium |
| **Load Shedding Status** | Medium | Small, Medium |
| **Billing Summary** | Medium | Small, Medium |
| **Device Overview** | Large | Medium, Large |
| **Alerts Summary** | Medium | Small, Medium |
| **AI Insights** | Medium | Small, Medium |
| **Peak Demand** | Medium | Small, Medium |

---

## Technical Implementation

### Files Modified/Created

#### Created:
```
frontend/src/components/dashboard/PresetPicker.tsx  ✨ NEW (300+ lines)
```

#### Modified:
```
frontend/src/contexts/DashboardLayoutContext.tsx     ✏️ Enhanced
frontend/src/components/dashboard/DashboardEditControls.tsx  ✏️ Enhanced
frontend/src/components/dashboard/DraggableWidget.tsx  ✏️ Enhanced
frontend/src/pages/Index.tsx  ✏️ Enhanced
```

### New Types & Interfaces

```typescript
// Widget size type
export type WidgetSize = "small" | "medium" | "large";

// Layout preset type
export type LayoutPreset = "essential" | "standard" | "comprehensive" | string;

// Updated WidgetConfig
export interface WidgetConfig {
  id: WidgetId;
  name: string;
  description: string;
  category: WidgetCategory;
  icon: string;
  defaultVisible: boolean;
  defaultSize: WidgetSize;  // ✨ NEW
  settings?: Record<string, unknown>;
}

// Updated LayoutItem
export interface LayoutItem {
  id: WidgetId;
  visible: boolean;
  size: WidgetSize;  // ✨ NEW
  settings: Record<string, unknown>;
}

// Preset configuration
export interface LayoutPresetConfig {
  id: LayoutPreset;
  name: string;
  description: string;
  widgets: Array<{
    id: WidgetId;
    visible: boolean;
    size: WidgetSize;
  }>;
}
```

### New Context Functions

```typescript
// Resize a widget
resizeWidget: (id: WidgetId, size: WidgetSize) => void;

// Apply a preset
applyPreset: (presetId: LayoutPreset) => void;

// Save current layout as custom preset
saveCustomPreset: (name: string, description: string) => void;

// Delete a custom preset
deleteCustomPreset: (presetId: string) => void;
```

### localStorage Keys

| Key | Purpose | Example Value |
|-----|---------|---------------|
| `dashboard-layout-v1` | Widget visibility & sizes | `[{id: "stat-cards", visible: true, size: "large", ...}]` |
| `dashboard-grid-layout-v1` | Grid layout mode | `"list"`, `"2x2"`, `"3x3"` |
| `dashboard-preset-v1` | Current preset ID | `"standard"`, `"custom-1234567890"` |
| `dashboard-custom-presets-v1` | User's custom presets | `[{id: "custom-...", name: "My Layout", ...}]` |

---

## Grid Layout Behavior

### List Layout
- **All sizes:** Full width (sizes ignored)
- **Stacking:** Vertical stack

### 2x2 Grid Layout
- **Small:** 1 column
- **Medium:** 2 columns (full width on desktop)
- **Large:** 2 columns (full width)
- **Responsive:** Single column on mobile

### 3x3 Grid Layout
- **Small:** 1 column
- **Medium:** 2 columns on desktop
- **Large:** 3 columns (full width on desktop)
- **Responsive:** Adapts to screen size

---

## User Flow Examples

### Example 1: New User Setup
1. User lands on dashboard (default: **Standard** preset)
2. Dashboard shows 8 core widgets in Medium/Large sizes
3. User can immediately see key metrics
4. User clicks "Edit Layout" to customize
5. User switches to **Essential** preset for cleaner view

### Example 2: Power User Customization
1. User switches to **Comprehensive** preset (all widgets)
2. User resizes some widgets to Small for compact view
3. User removes unwanted widgets
4. User saves as "My Custom View" preset
5. Preset is now available in preset picker

### Example 3: Preset Comparison
1. User opens Presets dialog
2. Sees all 3 built-in presets with descriptions
3. Sees widget counts (4, 8, 14 widgets)
4. Quickly switches between presets to test
5. Finds **Standard** preset works best

---

## Migration to Database (Future)

Current implementation uses localStorage. To migrate to database:

### Backend Changes Needed:

1. **Create user_dashboard_preferences table:**
```sql
CREATE TABLE user_dashboard_preferences (
  user_id UUID PRIMARY KEY,
  layout_preset VARCHAR(50),
  widget_layout JSONB,
  grid_layout VARCHAR(10),
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

2. **Create user_custom_presets table:**
```sql
CREATE TABLE user_custom_presets (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  name VARCHAR(100),
  description TEXT,
  widget_config JSONB,
  created_at TIMESTAMP
);
```

### Frontend Changes Needed:

1. Replace localStorage reads with API calls
2. Replace localStorage writes with API mutations
3. Add loading states for async operations
4. Add error handling for network failures

### API Endpoints Needed:

```typescript
// Get user preferences
GET /api/v1/users/me/dashboard-preferences

// Update user preferences
PUT /api/v1/users/me/dashboard-preferences
{
  layout_preset: "standard",
  widget_layout: [...],
  grid_layout: "2x2"
}

// Get custom presets
GET /api/v1/users/me/dashboard-presets

// Create custom preset
POST /api/v1/users/me/dashboard-presets
{
  name: "My Layout",
  description: "...",
  widget_config: [...]
}

// Delete custom preset
DELETE /api/v1/users/me/dashboard-presets/:id
```

---

## Testing Guide

### Test Case 1: Apply Built-in Presets
```
1. Navigate to dashboard
2. Click "Edit Layout"
3. Click "Presets" button
4. Select "Essential" → Click "Apply Preset"
   ✅ Should show only 4 widgets
5. Select "Comprehensive" → Click "Apply Preset"
   ✅ Should show all 14 widgets
6. Select "Standard" → Click "Apply Preset"
   ✅ Should show 8 widgets
```

### Test Case 2: Widget Resizing
```
1. Enter edit mode
2. Hover over Energy Flow widget
3. Click size icon (square/maximize/minimize)
4. Select "Small"
   ✅ Widget should resize to 1 column
5. Select "Large"
   ✅ Widget should expand to full width
6. Check preset badge
   ✅ Should change to "Custom"
```

### Test Case 3: Save Custom Preset
```
1. Customize dashboard (resize + hide/show widgets)
2. Click "Presets" → "Save Current as Preset"
3. Enter name: "Test Preset"
4. Enter description: "My test layout"
5. Click "Save Preset"
   ✅ Dialog should close
   ✅ Preset badge should show "Test Preset"
6. Reopen Presets dialog
   ✅ "Test Preset" should appear in Custom Presets section
```

### Test Case 4: Delete Custom Preset
```
1. Open Presets dialog
2. Find custom preset
3. Click trash icon
4. Confirm deletion
   ✅ Preset should be removed from list
   ✅ If active preset was deleted, should switch to "Standard"
```

### Test Case 5: Persistence
```
1. Apply a preset (e.g., Essential)
2. Resize some widgets
3. Refresh page
   ✅ Layout should persist
   ✅ Preset should be "Custom" (due to manual resize)
4. Apply Standard preset
5. Refresh page
   ✅ Should still be Standard preset
```

### Test Case 6: Grid Layout + Sizes
```
1. Switch to 2x2 grid
2. Set Energy Flow to "Large"
   ✅ Should span full width (2 columns)
3. Set Weather to "Small"
   ✅ Should take 1 column
4. Switch to 3x3 grid
5. Large widgets should span 3 columns
6. Medium widgets should span 2 columns
7. Small widgets should span 1 column
```

---

## Keyboard Shortcuts

No new keyboard shortcuts added. Use existing:
- **Cmd/Ctrl + K** → Open Command Palette
- **G + D** → Go to Dashboard

---

## Troubleshooting

### Preset not applying?
- Check browser console for errors
- Verify localStorage is not full
- Try clearing localStorage and refreshing

### Widget sizes not working?
- Make sure you're in edit mode
- Check that grid layout is 2x2 or 3x3 (not List)
- Small widgets in List mode will still be full width

### Custom preset not saving?
- Check that you entered a preset name
- Verify localStorage has space (quota ~5-10MB)
- Check browser console for errors

### Preset badge not updating?
- Manual widget resize changes preset to "Custom"
- This is expected behavior
- Save as new preset if you want to keep the layout

---

## Summary

✅ **3 Built-in Presets:** Essential, Standard, Comprehensive
✅ **Widget Resizing:** Small, Medium, Large for each widget
✅ **Custom Presets:** Save unlimited custom layouts
✅ **Persistence:** All settings saved to localStorage
✅ **Dynamic Grid:** Widget sizes adapt to grid layout
✅ **UI Integration:** Seamless preset picker + size controls

**Total Implementation:**
- **1 New Component:** PresetPicker (300+ lines)
- **4 Enhanced Components:** DashboardLayoutContext, DashboardEditControls, DraggableWidget, Index
- **3 Built-in Presets:** Configured with widget visibility & sizes
- **4 localStorage Keys:** For complete state persistence

**Next Steps:**
1. Test the implementation thoroughly
2. Gather user feedback on default sizes
3. Plan database migration for multi-device sync
4. Add analytics to track preset usage

🎉 **Enjoy your customizable dashboard!**
