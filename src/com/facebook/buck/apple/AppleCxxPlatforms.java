/*
 * Copyright 2014-present Facebook, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
 */

package com.facebook.buck.apple;

import com.facebook.buck.cxx.CxxPlatform;
import com.facebook.buck.cxx.DarwinLinker;
import com.facebook.buck.cxx.DebugPathSanitizer;
import com.facebook.buck.cxx.ImmutableCxxPlatform;
import com.facebook.buck.cxx.SourcePathTool;
import com.facebook.buck.cxx.Tool;
import com.facebook.buck.io.MoreFiles;
import com.facebook.buck.model.ImmutableFlavor;
import com.facebook.buck.rules.PathSourcePath;
import com.facebook.buck.rules.SourcePath;
import com.facebook.buck.util.HumanReadableException;
import com.facebook.buck.util.environment.Platform;
import com.google.common.base.Optional;
import com.google.common.base.Preconditions;
import com.google.common.collect.ImmutableBiMap;
import com.google.common.collect.ImmutableList;

import java.io.File;
import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * Utility class to create Objective-C/C/C++/Objective-C++ platforms to
 * support building iOS and Mac OS X products with Xcode.
 */
public class AppleCxxPlatforms {

  // Utility class, do not instantiate.
  private AppleCxxPlatforms() { }

  private static final Path USR_BIN = Paths.get("usr/bin");

  public static CxxPlatform build(
      Platform hostPlatform,
      ApplePlatform targetPlatform,
      String targetSdkName,
      String targetVersion,
      String targetArchitecture,
      AppleSdkPaths sdkPaths) {

    Preconditions.checkArgument(
        hostPlatform.equals(Platform.MACOS),
        String.format("%s can only currently run on Mac OS X.", AppleCxxPlatforms.class));

    // Search for tools from most specific to least specific.
    ImmutableList.Builder<Path> toolSearchPathsBuilder =
        ImmutableList.<Path>builder()
            .add(sdkPaths.getSdkPath().resolve(USR_BIN))
            .add(sdkPaths.getPlatformDeveloperPath().resolve(USR_BIN));
    for (Path toolchainPath : sdkPaths.getToolchainPaths()) {
      toolSearchPathsBuilder.add(toolchainPath.resolve(USR_BIN));
    }
    ImmutableList<Path> toolSearchPaths = toolSearchPathsBuilder.build();

    Tool clangPath = new SourcePathTool(getTool("clang", toolSearchPaths));
    Tool clangXxPath = new SourcePathTool(getTool("clang++", toolSearchPaths));

    ImmutableList.Builder<String> cflagsBuilder = ImmutableList.builder();
    cflagsBuilder.add("-isysroot", sdkPaths.getSdkPath().toString());
    cflagsBuilder.add("-arch", targetArchitecture);
    switch (targetPlatform) {
      case MACOSX:
        cflagsBuilder.add("-mmacosx-version-min=" + targetVersion);
        break;
      case IPHONESIMULATOR:
        // Fall through
      case IPHONEOS:
        cflagsBuilder.add("-mios-version-min=" + targetVersion);
        break;
    }
    // TODO(user): Add more and better cflags.
    ImmutableList<String> cflags = cflagsBuilder.build();

    return ImmutableCxxPlatform.builder()
        .setFlavor(ImmutableFlavor.of(targetSdkName + "-" + targetArchitecture))
        .setAs(clangPath)
        .setAspp(clangPath)
        .setCc(clangPath)
        .addAllCflags(cflags)
        .setCpp(clangPath)
        .addAllCppflags(cflags)
        .setCxx(clangXxPath)
        .addAllCxxflags(cflags)
        .setCxxpp(clangXxPath)
        .addAllCxxppflags(cflags)
        .setCxxld(clangXxPath)
        .addAllCxxldflags(cflags)
        .setLex(getOptionalTool("lex", toolSearchPaths))
        .setYacc(getOptionalTool("yacc", toolSearchPaths))
        .setLd(new DarwinLinker(new SourcePathTool(getTool("libtool", toolSearchPaths))))
        .setAr(new SourcePathTool(getTool("ar", toolSearchPaths)))
        .setDebugPathSanitizer(Optional.of(
            new DebugPathSanitizer(
                250,
                File.separatorChar,
                Paths.get("."),
                ImmutableBiMap.<Path, Path>of())))
        .setSharedLibraryExtension("dylib")
        .build();
  }

  private static Optional<SourcePath> getOptionalTool(
      String tool,
      ImmutableList<Path> toolSearchPaths) {
    Optional<Path> toolPath = MoreFiles.searchPathsForExecutable(Paths.get(tool), toolSearchPaths);
    if (toolPath.isPresent()) {
      return Optional.<SourcePath>of(new PathSourcePath(toolPath.get()));
    } else {
      return Optional.<SourcePath>absent();
    }
  }

  private static SourcePath getTool(
      String tool,
      ImmutableList<Path> toolSearchPaths) {
    Optional<SourcePath> result = getOptionalTool(tool, toolSearchPaths);
    if (!result.isPresent()) {
      throw new HumanReadableException(
        "Cannot find tool %s in paths %s",
        tool,
        toolSearchPaths);
    }
    return result.get();
  }

}
