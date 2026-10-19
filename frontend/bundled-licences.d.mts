import type { Plugin } from "vite";

/** The file a package's licence takes in the build output, under licences/. */
export function licenceFileName(name: string): string;

/** Copies the licence of every third-party package in the build to licences/ in its output. */
export function bundledLicences(): Plugin;
