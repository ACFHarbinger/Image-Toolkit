import React from "react";
import MangaWorkspaceView, { MangaWorkspaceViewProps } from "./MangaWorkspaceView";

export const MangaAnimationView: React.FC<MangaWorkspaceViewProps> = (props) => {
  return <MangaWorkspaceView {...props} initialMode="animation" />;
};

export default MangaAnimationView;
