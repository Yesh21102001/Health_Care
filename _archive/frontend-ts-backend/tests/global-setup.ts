import { MongoMemoryServer } from "mongodb-memory-server";
import type { TestProject } from "vitest/node";

declare module "vitest" {
  export interface ProvidedContext {
    mongoUri: string;
  }
}

/** Starts a throwaway MongoDB for the whole test run. No Atlas account needed. */
export default async function setup(project: TestProject) {
  const mongo = await MongoMemoryServer.create();
  project.provide("mongoUri", mongo.getUri("healthai-test"));
  return async () => {
    await mongo.stop();
  };
}
