import React from "react";
import MangaWorkspaceView, { MangaWorkspaceViewProps } from "./MangaWorkspaceView";

export const MangaColorizationView: React.FC<MangaWorkspaceViewProps> = (props) => {
  return <MangaWorkspaceView {...props} initialMode="colorization" />;
};

export default MangaColorizationView;
