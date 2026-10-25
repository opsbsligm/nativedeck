/* Minimal Vulkan capability probe: enumerates what a native Vulkan game would see.
   Built inside the build container, run on the SteamOS host so the host's own RADV ICD answers. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <vulkan/vulkan.h>

static const char *WANT[] = {
    VK_KHR_SWAPCHAIN_EXTENSION_NAME,
    "VK_EXT_vertex_attribute_divisor", "VK_EXT_transform_feedback", "VK_EXT_custom_border_color",
    "VK_KHR_shader_clock", "VK_KHR_shader_maximal_reconvergence", "VK_EXT_attachment_feedback_loop_layout",
    "VK_EXT_attachment_feedback_loop_dynamic_state", "VK_KHR_dynamic_rendering_local_read",
    "VK_EXT_conditional_rendering", "VK_EXT_provoking_vertex", "VK_EXT_pipeline_robustness",
    "VK_EXT_robustness2", "VK_EXT_memory_budget", "VK_EXT_calibrated_timestamps",
    "VK_EXT_external_memory_host", "VK_EXT_index_type_uint8", "VK_EXT_rasterization_order_attachment_access",
    "VK_KHR_portability_subset", "VK_KHR_video_queue", "VK_KHR_video_decode_queue",
    "VK_KHR_video_decode_h264", "VK_KHR_video_decode_h265", "VK_KHR_video_encode_h264",
    "VK_NV_shader_sm_builtins", "VK_EXT_shader_image_int64", "VK_EXT_64_bit_index",
    "VK_EXT_shader_atomic_float", "VK_EXT_nested_command_buffer_usage", "VK_EXT_device_address_binding_report",
    "VK_EXT_map_memory_placed", "VK_EXT_pageable_device_local_memory", "VK_EXT_memory_priority",
    "VK_EXT_descriptor_buffer", "VK_EXT_shader_object", "VK_EXT_graphics_pipeline_library",
    "VK_EXT_pipeline_binary_cache", "VK_KHR_dynamic_rendering", "VK_EXT_full_screen_exclusive",
    "VK_KHR_present_wait", "VK_KHR_present_id", "VK_EXT_swapchain_maintenance1", "VK_EXT_debug_utils",
};

static uint32_t cnt_cmp(const void *a, const void *b) { (void)a; (void)b; return 0; }
static int cmpstr(const void *a, const void *b) { return strcmp(*(const char **)a, *(const char **)b); }

int main(void) {
    VkApplicationInfo ai = {.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
                            .pApplicationName = "vkprobe", .apiVersion = VK_API_VERSION_1_3};
    VkInstanceCreateInfo ici = {.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO, .pApplicationInfo = &ai};
    VkInstance in;
    if (vkCreateInstance(&ici, NULL, &in) != VK_SUCCESS) { printf("FATAL: no instance\n"); return 1; }

    uint32_t n = 0;
    vkEnumerateInstanceExtensionProperties(NULL, &n, NULL);
    printf("instance: loader exposes %u extensions\n", n);

    vkEnumeratePhysicalDevices(in, &n, NULL);
    VkPhysicalDevice *pds = calloc(n ? n : 1, sizeof *pds);
    vkEnumeratePhysicalDevices(in, &n, pds);
    printf("physical devices: %u\n\n", n);

    for (uint32_t d = 0; d < n; d++) {
        VkPhysicalDeviceProperties p;
        vkGetPhysicalDeviceProperties(pds[d], &p);
        printf("=== [%u] %s\n", d, p.deviceName);
        printf("api 0x%08x driver 0x%08x vendor 0x%x deviceID 0x%x\n", p.apiVersion, p.driverVersion, p.vendorID,
               p.deviceID);
        VkPhysicalDeviceDriverProperties drv = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES};
        VkPhysicalDeviceProperties2 p2 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2, .pNext = &drv};
        vkGetPhysicalDeviceProperties2(pds[d], &p2);
        printf("driverName=%s driverInfo=%s driverID=%d\n", drv.driverName, drv.driverInfo, drv.driverID);

        uint32_t en = 0;
        vkEnumerateDeviceExtensionProperties(pds[d], NULL, &en, NULL);
        VkExtensionProperties *es = calloc(en ? en : 1, sizeof *es);
        vkEnumerateDeviceExtensionProperties(pds[d], NULL, &en, es);
        char **names = calloc(en ? en : 1, sizeof *names);
        for (uint32_t i = 0; i < en; i++) names[i] = es[i].extensionName;
        qsort(names, en, sizeof *names, cmpstr);
        (void)cnt_cmp;
        printf("device extensions: %u\n", en);
        for (uint32_t i = 0; i < en; i++) printf("EXT %s\n", names[i]);
        printf("WANT-MATRIX\n");
        for (uint32_t w = 0; w < sizeof WANT / sizeof *WANT; w++) {
            int found = 0;
            for (uint32_t i = 0; i < en; i++)
                if (!strcmp(names[i], WANT[w])) { found = 1; break; }
            printf("WANT %s %s\n", found ? "YES" : "NO ", WANT[w]);
        }
        free(names);
        free(es);

        VkPhysicalDeviceFeatures f;
        vkGetPhysicalDeviceFeatures(pds[d], &f);
        printf("FEAT textureCompressionASTC_LDR %d\n", f.textureCompressionASTC_LDR);
        printf("FEAT textureCompressionBC %d\n", f.textureCompressionBC);
        printf("FEAT textureCompressionETC2 %d\n", f.textureCompressionETC2);
        printf("FEAT geometryShader %d tessellationShader %d sparseBinding %d multiDrawIndirect %d\n",
               f.geometryShader, f.tessellationShader, f.sparseBinding, f.multiDrawIndirect);
        printf("FEAT occlusionQueryPrecise %d pipelineStatisticsQuery %d depthClamp %d\n", f.occlusionQueryPrecise,
               f.pipelineStatisticsQuery, f.depthClamp);

        VkPhysicalDeviceVulkan12Features f12 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES};
        VkPhysicalDeviceVulkan13Features f13 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES,
                                                .pNext = &f12};
        VkPhysicalDeviceFeatures2 f2 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2, .pNext = &f13};
        vkGetPhysicalDeviceFeatures2(pds[d], &f2);
        printf("F12 descriptorIndexing %d scalarLayout %d timelineSemaphore %d bufferDeviceAddress %d "
               "shaderFloat16 %d separateDepthStencil %d hostQueryReset %d\n",
               f12.descriptorIndexing, f12.timelineSemaphore, f12.bufferDeviceAddress,
               f12.shaderFloat16, f12.separateDepthStencilLayouts, f12.hostQueryReset);
        printf("F13 dynamicRendering %d synchronization2 %d pipelineCreationCacheControl %d "
               "shaderTerminateInvocation %d inlineUniformPlacement %d\n",
               f13.dynamicRendering, f13.synchronization2, f13.pipelineCreationCacheControl,
               f13.shaderTerminateInvocation, f13.inlineUniformBlock);

        uint32_t qn = 0;
        vkGetPhysicalDeviceQueueFamilyProperties(pds[d], &qn, NULL);
        VkQueueFamilyProperties *qs = calloc(qn ? qn : 1, sizeof *qs);
        vkGetPhysicalDeviceQueueFamilyProperties(pds[d], &qn, qs);
        for (uint32_t i = 0; i < qn; i++)
            printf("QUEUE %u flags 0x%x count %u\n", i, qs[i].queueFlags, qs[i].queueCount);
        free(qs);

        struct { VkFormat f; const char *n; } fmts[] = {
            {VK_FORMAT_ASTC_4x4_SRGB_BLOCK, "ASTC_4x4_SRGB"},
            {VK_FORMAT_ASTC_6x6_SRGB_BLOCK, "ASTC_6x6_SRGB"},
            {VK_FORMAT_ASTC_8x8_SRGB_BLOCK, "ASTC_8x8_SRGB"},
            {VK_FORMAT_BC7_UNORM_BLOCK, "BC7_UNORM"},
            {VK_FORMAT_ETC2_R8G8B8A8_SRGB_BLOCK, "ETC2_RGBA8_SRGB"},
        };
        for (unsigned i = 0; i < sizeof fmts / sizeof *fmts; i++) {
            VkFormatProperties2 fp = {.sType = VK_STRUCTURE_TYPE_FORMAT_PROPERTIES_2};
            vkGetPhysicalDeviceFormatProperties2(pds[d], fmts[i].f, &fp);
            unsigned opt = (unsigned)fp.formatProperties.optimalTilingFeatures;
            VkPhysicalDeviceImageFormatInfo2 ifi = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_IMAGE_FORMAT_INFO_2,
                                                   .format = fmts[i].f,
                                                   .type = VK_IMAGE_TYPE_2D,
                                                   .tiling = VK_IMAGE_TILING_OPTIMAL,
                                                   .usage = VK_IMAGE_USAGE_SAMPLED_BIT};
            VkImageFormatProperties2 ifp = {.sType = VK_STRUCTURE_TYPE_IMAGE_FORMAT_PROPERTIES_2};
            VkResult r = vkGetPhysicalDeviceImageFormatProperties2(pds[d], &ifi, &ifp);
            printf("FMT %s optimal 0x%x sampled_image %s\n", fmts[i].n, opt, r == VK_SUCCESS ? "OK" : "NO");
        }

        PFN_vkGetPhysicalDeviceCalibrateableTimeDomainsEXT gettd =
            (PFN_vkGetPhysicalDeviceCalibrateableTimeDomainsEXT)(void (*)(void))vkGetInstanceProcAddr(
                in, "vkGetPhysicalDeviceCalibrateableTimeDomainsEXT");
        uint32_t tn = 0;
        VkTimeDomainEXT *td = calloc(16, sizeof *td);
        if (gettd && gettd(pds[d], &tn, td) == VK_SUCCESS) {
            for (uint32_t i = 0; i < tn; i++)
                printf("TIME DOMAIN %d%s\n", td[i], td[i] == VK_TIME_DOMAIN_CLOCK_MONOTONIC_RAW_EXT ? " (CM_RAW)" : "");
        }
        free(td);

        VkPhysicalDeviceMemoryProperties mp;
        vkGetPhysicalDeviceMemoryProperties(pds[d], &mp);
        for (uint32_t i = 0; i < mp.memoryHeapCount; i++)
            printf("HEAP %u size %llu MB flags 0x%x\n", i, (unsigned long long)(mp.memoryHeaps[i].size >> 20),
                   mp.memoryHeaps[i].flags);
        printf("\n");
    }
    vkDestroyInstance(in, NULL);
    return 0;
}
